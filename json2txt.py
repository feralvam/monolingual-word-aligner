import argparse
import json
import os


def _format_token_info(sent_json):
    token_lst = sent_json['tokens']
    tokens = []
    sent_str = ""
    for token in token_lst:
        tokens.append(token['word'])
        sent_str += u"[Text={} CharacterOffsetBegin={} CharacterOffsetEnd={} PartOfSpeech={} Lemma={} NamedEntityTag={}] ".format(
            token['originalText'], token['characterOffsetBegin'], token['characterOffsetEnd'], token['pos'], token['lemma'], token['ner'])

    return tokens, sent_str


def _get_depnode_index(node_id, dep_parse):
    index = 0
    for dep_node in dep_parse:
        if dep_node['governor'] == node_id:
            return index
        index += 1


def _get_depnode_index_by_label(node_deplabel, dep_parse, node_ids):
    index = 0
    for dep_node in dep_parse:
        if dep_node['dep'] == node_deplabel and dep_node['governor'] in node_ids:
            return index
        index += 1


def process_json_sentence(sentence, sent_num=1):
    tokens, tokens_str = _format_token_info(sentence)

    dep_parse = sentence['basicDependencies']
    dep_parse_str = ""
    for dep_node in dep_parse:
        dep_rel = dep_node['dep'].lower()
        dependent_gloss = dep_node['dependentGloss']
        dependent = dep_node['dependent']

        if dep_rel == 'prep':
            aux_dep_node_index = _get_depnode_index(dep_node['dependent'], dep_parse)
            if aux_dep_node_index:
                dep_rel += u'_{}'.format(dep_node['dependentGloss'])
                aux_dep_node = dep_parse[aux_dep_node_index]
                dependent_gloss = aux_dep_node['dependentGloss']
                dependent = aux_dep_node['dependent']
        elif dep_rel == 'conj':
            aux_dep_node_index = _get_depnode_index_by_label('cc', dep_parse, [dep_node['dependent'], dep_node['governor']])
            if aux_dep_node_index:
                aux_dep_node = dep_parse[aux_dep_node_index]
                dep_rel += u'_{}'.format(aux_dep_node['dependentGloss'])
            else:
                continue
        elif dep_rel in ['cc', 'pobj']:
            continue

        dep_parse_str += u"{}({}-{}, {}-{})\n".format(dep_rel, dep_node['governorGloss'], dep_node['governor'],
                                                      dependent_gloss, dependent)

    info_str = u"Sentence #{} ({} tokens):\n".format(sent_num, len(tokens))
    info_str += ' '.join(tokens) + '\n'
    info_str += tokens_str + '\n'
    info_str += sentence['parse'] + '\n\n'
    info_str += dep_parse_str

    return info_str


def process_json_file(file_path, out_file_path, verbose=False):
    if verbose:
        print ("Processing file {}".format(file_path))
    with open(file_path) as json_file, open(out_file_path, 'w') as out_file:
        sentences = json.load(json_file)['sentences']
        sent_num = 0
        info_file = []
        for sent in sentences:
            sent_num += 1
            info_str = process_json_sentence(sent, sent_num)

            info_file.append(info_str)

        out_file.write('\n'.join(info_file).encode('utf8'))


if __name__ == '__main__':
    # create an Argument Parser to handle command line arguments
    parser = argparse.ArgumentParser(description="Transforms a json file to a out file from StanfordCoreNLP.")
    parser.add_argument('-file', help="a single json file")
    parser.add_argument('-filelist', help="a text file with the paths of several json files")

    args = parser.parse_args()

    if args.filelist:
        with open(args.filelist) as file_list:
            for json_file_path in file_list:
                out_file_path = os.path.splitext(json_file_path.strip())[0] + '.out'
                process_json_file(json_file_path.strip(), out_file_path)
    elif args.file:
        out_file_path = os.path.splitext(args.file)[0] + '.out'
        process_json_file(args.file, out_file_path)
    else:
        parser.print_help()

