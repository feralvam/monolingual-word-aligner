This is a fork of [Sultan et. al. (2014)](https://github.com/ma-sultan/monolingual-word-aligner) Monolingual Word Aligner.

It now relies on [stanford-corenlp](https://github.com/Lynten/stanford-corenlp) as a python wrapper for Stanford CoreNLP. This allows to use more up-to-date versions of the pipeline.

The aligner works in a similar fashion as its original version, but also adds support for aligning words in sentences that have been previously parsed. Run `python aligner_extra.py -h` for more information.
