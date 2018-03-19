import argparse
import json
import json2txt
import os
import re
import aligner


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


def read_text_file(file_path):
    with open(file_path) as infile:
        return infile.read().splitlines()


def read_json_file(file_path):
    with open(file_path) as infile:
        return json.load(infile)['sentences']


def group_sentence_alignments(sent1_lst, sent1_parse_lst, sent2_lst, sent2_parse_lst, sent_aligns):
    sent1_sents = []
    sent2_sents = []
    sent1_parse = []
    sent2_parse = []
    sent1_map = {}
    sent2_map = {}
    for index_pair in sent_aligns:
        sent1_index, sent2_index = map(int, index_pair.strip().split('\t'))

        sent1_added = sent1_index in sent1_map
        sent2_added = sent2_index in sent2_map

        if sent1_added and not sent2_added:  # it is a split
            sent_group_index = sent1_map[sent1_index]
            sent2_map[sent2_index] = sent_group_index
            sent2_sents[sent_group_index].append(sent2_lst[sent2_index])
            sent2_parse[sent_group_index].append(sent2_parse_lst[sent2_index])
        elif sent2_added and not sent1_added:  # it is a join
            sent_group_index = sent2_map[sent2_index]
            if len(sent2_sents[sent_group_index]) > 1:  # check to prevent M-to-N alignments
                sent_group_index = len(sent2_sents)
                sent2_map[sent2_index] = sent_group_index
                sent1_sents.insert(sent_group_index, [sent1_lst[sent1_index]])
                sent1_parse.insert(sent_group_index, [sent1_parse_lst[sent1_index]])
                sent2_sents.insert(sent_group_index, [sent2_lst[sent2_index]])
                sent2_parse.insert(sent_group_index, [sent2_parse_lst[sent2_index]])
            else:
                sent1_map[sent1_index] = sent_group_index
                sent1_sents[sent_group_index].append(sent1_lst[sent1_index])
                sent1_parse[sent_group_index].append(sent1_parse_lst[sent1_index])
        elif not sent1_added and not sent2_added:  # it is at least a 1-to-1
            sent_group_index = len(sent1_sents)
            sent1_map[sent1_index] = sent_group_index
            sent2_map[sent2_index] = sent_group_index
            sent1_sents.insert(sent_group_index, [sent1_lst[sent1_index]])
            sent1_parse.insert(sent_group_index, [sent1_parse_lst[sent1_index]])
            sent2_sents.insert(sent_group_index, [sent2_lst[sent2_index]])
            sent2_parse.insert(sent_group_index, [sent2_parse_lst[sent2_index]])
        # else: sent1_added and sent2_added:  # it is a M-to-N (not supported)

    return zip(sent1_sents, sent1_parse, sent2_sents, sent2_parse)


if __name__ == '__main__':
    # create an Argument Parser to handle command line arguments
    parser = argparse.ArgumentParser(description="uses the monolingual-word-aligner on already parsed sentences")

    parser.add_argument('sent1path', help="file with sentences (one per line) to align from.")
    parser.add_argument('sent2path', help="file with sentence (one per line) to align to.")
    parser.add_argument('sent1parsepath', help="json file with parsed sentences to align from.")
    parser.add_argument('sent2parsepath', help="json file with parsed sentences to align to.")
    parser.add_argument('-sentalignspath', help="file with the sentence alignments. If not given, 1-to-1 is assumed.")
    parser.add_argument('-outputfilename', help="name of the file with the word alignments.", default='aligns.mwa')
    parser.add_argument('-outputfolder', help="folder where to put the file with the word alignments.", default="./")

    args = parser.parse_args()

    sent1_lst = read_text_file(args.sent1path)
    sent2_lst = read_text_file(args.sent2path)

    sent1_parse_lst = read_json_file(args.sent1parsepath)
    sent2_parse_lst = read_json_file(args.sent2parsepath)

    sent_aligns = read_text_file(args.sentalignspath)

    sents_info = group_sentence_alignments(sent1_lst, sent1_parse_lst, sent2_lst, sent2_parse_lst, sent_aligns)

    word_aligns = []
    for sent1_text, sent2_text, sent1_parse_json, sent2_parse_json in sents_info:
        sent1_parse_text = json2txt.process_json_sentence(sent1_parse_json)
        sent2_parse_text = json2txt.process_json_sentence(sent2_parse_json)

        sent1_parse_file_result = parse_parser_results(sent1_parse_text)
        sent2_parse_file_result = parse_parser_results(sent2_parse_text)

        sent1_parse_result = dict()
        sent1_parse_result['sentences'] = [sent1_parse_file_result['sentences'][i] for i, _ in enumerate(sent1_text)]

        sent2_parse_result = dict()
        sent2_parse_result['sentences'] = [sent2_parse_file_result['sentences'][i] for i, _ in enumerate(sent2_text)]

        # get the alignments (only indices)
        aligns = aligner.align(sent1_parse_result, sent2_parse_result)
        # convert to pharaoh format: [[1, 1], [2, 2]] -> ['1-1', '2-2']
        alignsPharaoh = ['-'.join([str(p[0]), str(p[1])]) for p in aligns]
        # create a single line to write: ['1-1', '2-2'] -> '1-1 2-2'
        alignsLine = ' '.join(alignsPharaoh)
        word_aligns.append(alignsLine)

    aligns_file_path = os.path.join(args.outputfolder, args.outputfilename)
    with open(aligns_file_path, 'w') as aligns_file_path:
        aligns_file_path.write('\n'.join(word_aligns))
