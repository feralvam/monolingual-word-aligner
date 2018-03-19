import argparse
import re
from aligner import align


STATE_START, STATE_TEXT, STATE_WORDS, STATE_TREE, STATE_DEPENDENCY, STATE_COREFERENCE = 0, 1, 2, 3, 4, 5
WORD_PATTERN = re.compile('\[([^\]]+)\]')
CR_PATTERN = re.compile(r"\((\d*),(\d)*,\[(\d*),(\d*)\]\) -> \((\d*),(\d)*,\[(\d*),(\d*)\]\), that is: \"(.*)\" -> \"(.*)\"")


def parse_bracketed(s):
    """
    Parse word features [abc=... def = ...]
    Also manages to parse out features that have XML within them
    """
    word = None
    attrs = {}
    temp = {}
    # Substitute XML tags, to replace them later
    for i, tag in enumerate(re.findall(r"(<[^<>]+>.*<\/[^<>]+>)", s)):
        temp["^^^%d^^^" % i] = tag
        s = s.replace(tag, "^^^%d^^^" % i)
    # Load key-value pairs, substituting as necessary
    for attr, val in re.findall(r"([^=\s]*)=([^=\s]*)", s):
        if val in temp:
            val = temp[val]
        if attr == 'Text':
            word = val
        else:
            attrs[attr] = val
    return (word, attrs)


def parse_parser_results(text):
    """
    This is the nasty bit of code to interact with the command-line interface of the CoreNLP tools.
    Takes a string of the parser results and then returns a Python list of dictionaries, one for each parsed sentence.
    """
    results = {"sentences": []}
    state = STATE_START
    text = unicode(text, "utf-8")
    for line in text.split("\n"):
        line = line.strip()

        if line.startswith("Sentence #"):
            sentence = {'words': [], 'parsetree': [], 'dependencies': []}
            results["sentences"].append(sentence)
            state = STATE_TEXT

        elif state == STATE_TEXT:
            sentence['text'] = line
            state = STATE_WORDS

        elif state == STATE_WORDS:
            if not line.startswith("[Text="):
                raise Exception('Parse error. Could not find "[Text=" in: %s' % line)
            for s in WORD_PATTERN.findall(line):
                sentence['words'].append(parse_bracketed(s))
            state = STATE_TREE

        elif state == STATE_TREE:
            if len(line) == 0:
                state = STATE_DEPENDENCY
                sentence['parsetree'] = " ".join(sentence['parsetree'])
            else:
                sentence['parsetree'].append(line)

        elif state == STATE_DEPENDENCY:
            if len(line) == 0:
                state = STATE_COREFERENCE
            else:
                split_entry = re.split("\(|, ", line[:-1])
                if len(split_entry) == 3:
                    rel, left, right = split_entry
                    sentence['dependencies'].append([rel, left, right])

        elif state == STATE_COREFERENCE:
            if "Coreference set" in line:
                if 'coref' not in results:
                    results['coref'] = []
                coref_set = []
                results['coref'].append(coref_set)
            else:
                for src_i, src_pos, src_l, src_r, sink_i, sink_pos, sink_l, sink_r, src_word, sink_word in CR_PATTERN.findall(
                        line):
                    src_i, src_pos, src_l, src_r = int(src_i) - 1, int(src_pos) - 1, int(src_l) - 1, int(src_r) - 1
                    sink_i, sink_pos, sink_l, sink_r = int(sink_i) - 1, int(sink_pos) - 1, int(sink_l) - 1, int(
                        sink_r) - 1
                    coref_set.append(
                        ((src_word, src_i, src_pos, src_l, src_r), (sink_word, sink_i, sink_pos, sink_l, sink_r)))

    return results


if __name__ == '__main__':
    # create an Argument Parser to handle command line arguments
    parser = argparse.ArgumentParser(description="uses the monolingual-word-aligner on already parsed sentences")

    parser.add_argument('sent1path', help="file with sentences (one per line) to align from.")
    parser.add_argument('sent2path', help="file with sentence (one per line) to align to.")
    parser.add_argument('sent1parsepath', help="json file with parsed sentences to align from.")
    parser.add_argument('sent2parsepath', help="json file with parsed sentences to align to.")
    parser.add_argument('-outputfilename', help="name of the file with the word alignments.")
    parser.add_argument('-outputfolder', help="folder where to put the file with the word alignments.", default="./")

    args = parser.parse_args()

    sent1_path = args.sent1path
    sent2_path = args.sent2path
    sent1_parse_path = args.sent1parsepath
    sent2_parse_path = args.sent2parsepath
    out_folder = args.outputfolder

    if not args.outputfilename:
        aligns_file_path = out_folder + "aligns.mwa"

    with open(sent1_path) as sent1_file, open(sent2_path) as sent2_file, open(sent1_parse_path) as sent1_parse_file, \
            open(sent2_parse_path) as sent2_parse_file, open(aligns_file_path, 'w') as aligns_file:

        src_parse_file_result = parse_parser_results(srcParseFile.read())
        ref_parse_file_result = parse_parser_results(refParseFile.read())

        i = 0
        j = 0
        n = 1

        for sent_pair in sentsFile:
            # get the sentences
            src, ref = sent_pair.split('|||')

            src_parse_result = {'sentences': []}
            for src_sent in src.split('\t'):
                src_info = src_parse_file_result['sentences'][i]
                src_parse_result['sentences'].append(src_info)
                i+=1

            ref_parse_result = {'sentences': []}
            for ref_sent in ref.split('\t'):
                ref_info = ref_parse_file_result['sentences'][j]
                ref_parse_result['sentences'].append(ref_info)
                j+=1

            # get the alignments (only indices)
            aligns = align(src.strip(), ref.strip(), src_parse_result, ref_parse_result)
            # convert to pharaoh format: [[1, 1], [2, 2]] -> ['1-1', '2-2']
            alignsPharaoh = ['-'.join([str(p[0]), str(p[1])]) for p in aligns]
            # create a single line to write: ['1-1', '2-2'] -> '1-1 2-2'
            alignsLine = ' '.join(alignsPharaoh)
            aligns_file.write(alignsLine + '\n')

            n += 1
