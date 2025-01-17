
import re
from ekphrasis.classes.segmenter import Segmenter
from abbreviations import abbreviations
from nltk.stem import WordNetLemmatizer
#from nltk.stem import PorterStemmer
from collections import defaultdict
from nltk.corpus import stopwords
from nltk.corpus import wordnet
from nltk import pos_tag

class Preprocessing:

	def __init__(self, segmenter):
		# Segmenter using the word statistics from Wikipedia
		self.seg = segmenter
		#self.porter_stemmer = PorterStemmer()
		self.wordnet_lemmatizer = WordNetLemmatizer()
		self.en_stopwords = set(stopwords.words('english'))

	def __check_for_abbreviations(self, text):
		"""
			Replace abbreviations using a dictionary

			Args:
				text(list): list of words in a predicate
			Returns:
				list of the same words but abbreviations replaced by the full word
		"""
		full_words = []
		for word in text:
			if word in abbreviations:
				full_words += abbreviations[word].split()
			else:
				full_words.append(word)
		return full_words

	def __remove_special_characters_from_list(self,literals):
		"""
			Remove special characters from string

			Args:
				literals(list): list of predicates/literals
			Returns:
				list of the same predicates/literals with no special characters
		"""
		for i in range(len(literals)):
			literals[i] = self.__remove_special_characters(literals[i])
		return literals

	def __remove_special_characters(self,string):
		"""
			Remove special characters from string

			Args:
				string(array): predicate/literal
			Returns:
				string with no special characters
		""" 
		return re.sub('[^A-Za-z0-9]+', '', string)

	def __remove_stopwords(self, predicate):
		"""
			Remove stopwords from string

			Args:
				predicate(str): list of predicate/literal
			Returns:
				the same predicate/literal with no stopwords
		"""
		return [word for word in predicate if word not in self.en_stopwords]

	def __segment(self, text):
		"""
			Remove special characters from string

			Args:
				atoms(list): list of predicates/literals
			Returns:
				list of the same predicates/literals with no special characters
		"""

		# Tokenize (segment) the predicates into words
		# wasbornin -> was, born, in
		return self.seg.segment(text)

	def pre_process_text(self, text):
		"""
			Data preprocessing

			Args:
				text(str): a single predicate
			Returns:
				the predicate after lemma
		"""
		tag_map = defaultdict(lambda : wordnet.NOUN)
		tag_map['V'] = wordnet.VERB

		predicate = []
		for token, tag in pos_tag(self.__check_for_abbreviations(self.__segment(text).split())):
			# If it's a verb or a noun in plural, we apply lemmatization
			if token == 'as':
				predicate.append(token)
				continue
			predicate.append(self.wordnet_lemmatizer.lemmatize(token, tag_map[tag[0]]))
		return predicate


#from ekphrasis.classes.segmenter import Segmenter
#segmenter = Segmenter(corpus="english")

#test = Preprocessing(segmenter)
#print(test.pre_process_text('actorhasmembersofproject'))