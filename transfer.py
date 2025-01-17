
from gensim.test.utils import datapath, get_tmpfile
from gensim.models import KeyedVectors, Word2Vec
from preprocessing import Preprocessing
from collections import OrderedDict
from similarity import Similarity
from hungarian import Hungarian
import parameters as params
from scipy import spatial
import utils as utils
import pandas as pd
import numpy as np
import operator
import sys
import os
import re

class Transfer:

  def __init__(self, model, model_name, segmenter, similarity_metric, sources, targets, experiment, experiment_type):
    self.model = model
    self.model_name = model_name
    self.preprocessing = Preprocessing(segmenter)
    self.similarity_metric = similarity_metric
    self.sources = sources
    self.targets = targets
    self.experiment_title = experiment
    self.experiment_type = experiment_type

    self.similarity_matrix, self.dictionary = '', ''
    if self.similarity_metric == 'softcosine':
      self.similarity_matrix, self.dictionary = utils.get_softcosine_matrix(self.sources, self.targets, self.model, self.preprocessing)
    
    self.similarity = Similarity(self.preprocessing, self.similarity_matrix, self.dictionary)

  def __same_arity(self, source_literals, target_literals):
    """
        Check if predicates have the same arity

        Args:
            source_literals(list): source literals
            target_literals(list): target literals
       Returns:
            False if different arity
            True if same arity
    """
    return len(source_literals) == len(target_literals)

  def __is_compatible(self, source, target):
    """
        Check for type constraints
        Example: Given that both predicates have the type person, we can create the constraint person -> person
        Then, predicates actor(person) and director(person) are compatible
        Predicates publication(person, title) and projectmember(person,project) are also compatible and we can create a new constraint: title -> project
        However, predicates publication(person,title) and samecourse(course,course) are not compatible given the current constraints.

        Args:
            source(str): source predicate
            target(str): target predicate

       Returns:
            False if literals are not compatible
            True if literals are compatible
    """
    source_literals, target_literals = utils.get_all_literals([source]), utils.get_all_literals([target])
    if(self.__same_arity(source_literals, target_literals)):
      for source_literal, target_literal in zip(source_literals, target_literals):
        if(source_literal in self.constraints):
          if(self.constraints[source_literal] != target_literal):
            return False
        else:
          self.constraints[source_literal] = target_literal
      return True
    return False

  def __build_fasttext_array(self, data):
    """
        Turn relations into a single array

        Args:
            data(array): an array containing predicates for each tree
       Returns:
            a dictionary that the keys are the words and the values are single arrays of embeddings
    """

    def __get_vector(example):
      temp = []

      predicate = self.preprocessing.pre_process_text(example[0])
          
      for word in predicate:
        try:
          #temp.append(model.get_word_vector(word.lower().strip()))
          temp.append(self.model[word.lower().strip()])
        except:
          print('Word \'{}\' not present in pre-trained model'.format(word.lower().strip()))
          temp.append([0] * params.EMBEDDING_DIMENSION)
      return temp

    dict = {} 
    for example in data:
      #predicate = temp.copy()
      #if(params.METHOD):
      #  predicate = utils.single_array(temp, params.METHOD)

      if(params.INCLUDE_TYPES):
        # In the case the predicate has two arguments, ex: publication(person, movie)
        if(len(example[1]) > 1):
            dict[example[0].strip()] = [__get_vector(example), example[1], __get_vector([example[1][0]]), __get_vector([example[1][1]])]
        else:
          # In the case the predicate has only one argument, ex: director(person)
            dict[example[0].strip()] = [__get_vector(example), example[1], __get_vector([example[1][0]])]
      else:
        # Creates the embedding for the predicate
        dict[example[0].strip()] = [__get_vector(example), example[1]]
    return dict

  def __build_word2vec_array(self, data):
    """
        Turn relations into a single array

        Args:
            data(array): an array containing all predicates
       Returns:
            a dictionary that the keys are the words and the values are single arrays of embeddings
    """

    dict = {}
    for example in data:
      temp = []

      # Tokenize words of relation
      predicate = self.preprocessing.pre_process_text(example[0])

      for word in predicate:
        try:
          #temp.append(model.get_word_vector(word.lower().strip()))
          temp.append(self.model[word.lower().strip()])
        except:
          print(f'NOT FOUND {word.lower().strip()}')
          print('Word \'{}\' not present in pre-trained model'.format(word.lower().strip()))
          temp.append([0] * params.EMBEDDING_DIMENSION)

      #predicate = temp.copy()
      #if(params.METHOD):
      #  predicate = utils.single_array(temp, params.METHOD)

      dict[example[0].strip()] = [temp, example[1]]
    return dict

  def __build_word_vectors(self, data, similarity_metric):
    """
        Create word vectors if needed (given the similarity metric)

        Args:
            data(list): all triples of predicates
        Returns:
            a dictionary of word vectors or a list of strings
    """
    if(similarity_metric in params.WORD_VECTOR_SIMILARITIES):
      if(self.model_name == params.FASTTEXT):
        return self.__build_fasttext_array(data)
      else:
        return self.__build_word2vec_array(data)
      raise 'In build_words_vectors: model name should  be \'fasttext\' or \'word2vec\''
    return data

  def __find_best_single_mapping(self, clause, targets, similarity_metric, targets_taken={}, similarity_matrix='', dictionary='', allowSameTargetMap=False):
    """
        Calculate pairs similarity and sorts dataframe to obtain the closest target to a given source
        Args:
            clause(str): source clause
            targets(list): all targets found in the target domain
            similarity_metric(str): similarity metric to be applied
            targets_taken(list): forbidden target-predicates
        Returns:
            the closest target-predicate to the given source
      """

    source  = self.__build_word_vectors([utils.build_triple(clause)], similarity_metric)
    
    similarities = {}

    #import time 
    #start = time.time()

    #
    # Linha criada pra rodar os experimentos no cluster porque não consegui criar os modelos do SpaCy
    # 
    if(similarity_metric == 'relax-wmd'):
      import pandas as pd
      similarities = pd.read_csv(params.ROOT_PATH + 'resources/{}/rwmd-similarities-w-stop/{}_similarities.csv'.format(self.experiment_title,clause.split('(')[0])).set_index('candidates')
    else:
      similarities = self.similarity.compute_similarities(source, targets, similarity_metric, self.model, self.model_name)
    
    similarities.to_csv(params.ROOT_PATH + '{}/{}/similarities/{}/{}/{}_similarities.csv'.format(self.experiment_type, self.experiment_title, self.model_name, similarity_metric, clause.split('(')[0]))

    indexes = similarities.index.tolist()

    for index in indexes:
      index = re.split(r',\s*(?![^()]*\))', index)
      source, target = index[0].rstrip(), index[1].rstrip()

      # Literals must match
      if(not self.__same_arity(utils.get_all_literals([source]), utils.get_all_literals([target]))):
        continue
      
      if(allowSameTargetMap):
        return target, targets_taken
      else:
        if(target.split('(')[0] in targets_taken):
          continue
        else:
          targets_taken[target.split('(')[0]] = 0
          return target, targets_taken
    return '', targets_taken

  def __find_best_mapping(self, clause, targets, similarity_metric, targets_taken={}):
    """
        Calculate pairs similarity and sorts dataframe to obtain the closest target to a given source

        Args:
            clause(str): source clause
            targets(list): all targets found in the target domain
            similarity_metric(str): similarity metric to be applied
        Returns:
            the closest target-predicate to the given source
      """

    source  = self.__build_word_vectors([utils.build_triple(clause)], similarity_metric)
    
    similarities = {}
    
    #
    # Linha criada pra rodar os experimentos no cluster porque não consegui criar os modelos do SpaCy
    # 
    if(similarity_metric == 'relax-wmd'):
      import pandas as pd
      similarities = pd.read_csv(params.ROOT_PATH + 'resources/{}/rwmd-similarities-w-stop/{}_similarities.csv'.format(self.experiment_title,clause.split('(')[0])).set_index('candidates')
    else:
      similarities = self.similarity.compute_similarities(source, targets, similarity_metric, self.model, self.model_name)
      similarities.to_csv(params.ROOT_PATH + '{}/{}/similarities/{}/{}/{}_similarities.csv'.format(self.experiment_type, self.experiment_title, self.model_name, similarity_metric, clause.split('(')[0]))

    indexes = similarities.index.tolist()

    targets = []

    for index in indexes:
      index = re.split(r',\s*(?![^()]*\))', index)
      source, target = index[0].rstrip(), index[1].rstrip()

      # Literals must match
      if(not self.__same_arity(utils.get_all_literals([source]), utils.get_all_literals([target]))):
        continue

      if(params.ALLOW_SAME_TARGET_MAP or target.split('(')[0] not in targets_taken):
        targets.append(target)
        targets_taken[target.split('(')[0]] = 0

      #if(len(targets) == params.TOP_N):
      #  return targets, targets_taken
    return targets, targets_taken

  def map_predicates(self, similarity_metric, trees, targets):
    """
      Create mappings from source to target predicates using the order they appear in the structure

      Args:
          similarity_metric(str): similarity metric to be applied
          trees(list): all clauses learned from the source domain
          targets(list): all predicates found in the target domain

      Returns:
          all sources mapped to the its closest target-predicate
    """

    targets = utils.build_triples(targets)
    targets = self.__build_word_vectors(targets, similarity_metric)

    # For RWMD
    mapping_time = 0

    mappings, targets_taken = {}, {}
    for tree in trees:
      for i in range(len(tree.keys())):
        #Process ith node
        clauses = re.split(r',\s*(?![^()]*\))', tree[i])
        for clause in clauses:
          if(clause not in mappings and 'recursion' not in clause):
            if(params.TOP_N == 1):
              best_match, targets_taken = self.__find_best_single_mapping(clause, targets, similarity_metric, targets_taken)
              mappings[clause] = [best_match] if best_match != '' else []
            else:
              mappings[clause], targets_taken = self.__find_best_mapping(clause, targets, similarity_metric, targets_taken)

            #for RWMD
            if(similarity_metric == 'relax-wmd'):
              with open(params.ROOT_PATH + 'resources/{}/rwmd-similarities-w-stop/{}time.txt'.format(self.experiment_title,clause.split('(')[0]), 'r') as file:
                mapping_time += float(file.read())
    
    if(similarity_metric == 'relax-wmd'):
      return mappings, mapping_time
    
    return mappings

  def __find_most_similar_mapping(self, sources, targets, similarities):
    """
        Calculate pairs similarity and sorts dataframe to obtain the closest target to a given source

        Args:
            sources(list): list of source predicates
            targets(list): all targets found in the target domain
            similarities(DataFrame): similarities between (source, target) pairs of predicates
        Returns:
            the closest target-predicate to a given source
      """

    targets_taken = []
    mappings = {}

    for source in sources:
      mappings[source] = []

    indexes = similarities.index.tolist()
    for index in indexes:
      index = re.split(r',\s*(?![^()]*\))', index)
      source, target = index[0].rstrip().replace('`', ''), index[1].rstrip().replace('`', '')

      #if(source in mappings and len(mappings[source]) == params.TOP_N):
      #  continue

      # Literals must match
      if(not self.__same_arity(utils.get_all_literals([source]), utils.get_all_literals([target]))):
        continue

      if(params.ALLOW_SAME_TARGET_MAP or target.split('(')[0] not in targets_taken):
        mappings[source].append(target)
        targets_taken.append(target.split('(')[0])
        
    return mappings
  
  def map_predicates_most_similar(self, similarity_metric, clauses, targets):
    """
      Create mappings from source to target predicates

      Args:
          similarity_metric(str): similarity metric to be applied
          trees(list): all clauses learned from the source domain
          targets(list): all predicates found in the target domain

      Returns:
          all sources mapped to the its closest target-predicate
    """

    targets = utils.build_triples(targets)
    targets = self.__build_word_vectors(targets, similarity_metric)

    # For RWMD
    mapping_time = 0

    mappings, targets_taken = {}, {}
    similarities = pd.DataFrame()
    clauses = list(set(clauses))

    for clause in clauses:
      if('recursion' in clause):
        continue
        
      source  = self.__build_word_vectors([utils.build_triple(clause)], similarity_metric)

      if(similarity_metric == 'relax-wmd'):
        current = pd.read_csv(params.ROOT_PATH + 'resources/{}/rwmd-similarities-w-stop/{}_similarities.csv'.format(self.experiment_title,clause.split('(')[0])).set_index('candidates')
      else:
        current = self.similarity.compute_similarities(source, targets, similarity_metric, self.model, self.model_name)
        current.to_csv(params.ROOT_PATH + '{}/{}/similarities/{}/{}/{}_similarities.csv'.format(self.experiment_type, self.experiment_title, self.model_name, similarity_metric, clause.split('(')[0]))
      similarities = pd.concat([similarities, current])

    if(similarity_metric == 'softcosine'):
      similarities = similarities.rename_axis('candidates').sort_values(by=['similarity', 'candidates'], ascending=[False, True])
    else:
      similarities = similarities.rename_axis('candidates').sort_values(by=['similarity', 'candidates'])

    if(params.USE_HUNGARIAN_METHOD):
      if(similarity_metric == 'softcosine'):
        similarities['similarity'] = 1 - similarities['similarity']
        
      hug = Hungarian(similarities)
      mappings = hug.assigment()
      del hug
    else:
      mappings = self.__find_most_similar_mapping(clauses, targets, similarities)

    if(similarity_metric == 'relax-wmd'):
      clause = clause.replace('recursion_', '') if 'recursion_' in clause else clause

      with open(params.ROOT_PATH + 'resources/{}/rwmd-similarities-w-stop/{}time.txt'.format(self.experiment_title,clause.split('(')[0]), 'r') as file:
        mapping_time += float(file.read())
      return mappings, mapping_time

    return mappings

  def write_constraints_to_file(self, filename):
    """
          Write constraints file

          Args:
              similarity_metric(str): similarity metric
              embedding_model(str): model name
              mapping(dict): a dictionary a pair of literal mapping (source, target)
              filename(str): file path
         Returns:
              writes a file containing transfer information
    """
    with open(filename + '/constraints.txt', 'w') as file:
      for source in self.constraints.keys():
        if(self.constraints[source] != ''):
          file.write((source.replace('`', '') + ': ' +  self.constraints[source]).replace('`', ''))
        else:
          file.write((source.replace('`', '') + ':'))
        file.write('\n')

  def write_to_file_closest_distance(self, similarity_metric, model_name, from_predicate, to_predicate, arity, mapping, filename, recursion=False, searchArgPermutation=False, searchEmpty=False, allowSameTargetMap=False):
    """
          Write transfer file

          Args:
              from_predicate(str): predicate of model trained using source data
              to_predicate(str): predicate of model to be trained transfering the structure of source model
              arity(int): arity of from and to predicate
              mapping(dict): a dictionary a pair of mapping (source, target)
         Returns:
              writes a file containing transfer information
    """
    with open(params.TRANSFER_FILENAME, 'w') as file:
      for source in mapping.keys():
        if(mapping[source]):
          file.write((source.replace('`', '') + ': ' +  ','.join(mapping[source])).replace('`', ''))
        else:
          file.write((source.replace('`', '') + ':'))
        file.write('\n')

      if(recursion):
          file.write('recursion_' + from_predicate + '(A,B): recursion_' + to_predicate + '(A,B)\n')
      file.write('setMap:' + from_predicate + '(' + ','.join([chr(65+i) for i in range(arity)]) + ')' + ',' + to_predicate + '(' + ','.join([chr(65+i) for i in range(arity)]) + ')' + '\n')
      file.write('setParam:searchArgPermutation=' + str(searchArgPermutation).lower() + '.\n')
      file.write('setParam:searchEmpty=' + str(searchEmpty).lower() + '.\n')
      file.write('setParam:allowSameTargetMap=false.\n')  #+ str(allowSameTargetMap).lower() + '.\n')
      file.write('setParam:N=' + str(params.TOP_N) + '.\n')

    with open(filename + '/transfer_{}_{}.txt'.format(model_name, similarity_metric), 'w') as file:
      for source in mapping.keys():
        if(mapping[source] != ''):
          file.write((source.replace('`', '') + ': ' +  ','.join(mapping[source])).replace('`', ''))
        else:
          file.write((source.replace('`', '') + ':'))
        file.write('\n')

      if(recursion):
          file.write('recursion_' + from_predicate + '(A,B): recursion_' + to_predicate + '(A,B)\n')
      file.write('setMap:' + from_predicate + '(' + ','.join([chr(65+i) for i in range(arity)]) + ')' + ',' + to_predicate + '(' + ','.join([chr(65+i) for i in range(arity)]) + ')' + '\n')
      file.write('setParam:searchArgPermutation=' + str(searchArgPermutation).lower() + '.\n')
      file.write('setParam:searchEmpty=' + str(searchEmpty).lower() + '.\n')
      file.write('setParam:allowSameTargetMap=false.\n')  #+ str(allowSameTargetMap).lower() + '.\n')
      file.write('setParam:N=' + str(params.TOP_N) + '.\n')
