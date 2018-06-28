import json
import sys

filePath = sys.argv[1]
fileDir = sys.argv[2]
fileName = filePath.split('/')[-1]

with open(filePath, 'r') as jsonFile, open(fileDir + fileName + '.stp', 'w') as stpFile:
    sentences = json.load(jsonFile)['sentences']
    for sent in sentences:
        parse = ' '.join(sent['parse'].split())
        stpFile.write(parse + '\n')
