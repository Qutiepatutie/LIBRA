from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

# Team-maintained starting list (spec 4.7).
LIBRARY_WORDS = frozenset({"study", "research", "researchers", "respondents", "thesis", "chapter", "book", "edition"})

# Common Filipino function words.
FILIPINO_WORDS = frozenset({"ang", "ng", "sa", "mga", "na", "at", "ay", "ito", "para", "kung", "si", "ni", "kay",
                            "nang", "pa"})

# Generic research-title words. Number of titles containing each word among the 277 sample titles
# (spec 4.7): selected 18, level 19, basis 18, evaluation 22, assessment 15, determination 13,
# implementation 12, development 16, impact 14, based 13, iii 15.
THESIS_TITLE_WORDS = frozenset({"selected", "level", "basis", "evaluation", "assessment", "determination",
                                "implementation", "development", "impact", "based", "iii"})

# Philippine place words: where a study was done, not what it is about. Title counts in the sample
# (spec 4.7): city 48, pampanga 27, bulacan 16, angeles 13, san 14, marilao 10, region 17, province 11,
# district 11; caloocan was found in the titles without a recorded count.
PLACE_WORDS = frozenset({"city", "pampanga", "bulacan", "angeles", "san", "marilao", "region", "province",
                         "district", "caloocan"})

# Generic textbook title words. Title counts in the 385-book sample (spec 16.2): guide 22,
# introduction 17, principles 11, basic 11, applications 11, approach 11, fundamentals 10, concepts 8,
# practice 8, essentials 6; applied, volume and part have no recorded count.
BOOK_TITLE_WORDS = frozenset({"guide", "introduction", "principles", "basic", "applications", "approach",
                              "fundamentals", "concepts", "practice", "essentials", "applied", "volume", "part"})

STOP_WORDS = sorted(
    set(ENGLISH_STOP_WORDS) | LIBRARY_WORDS | FILIPINO_WORDS | THESIS_TITLE_WORDS | PLACE_WORDS | BOOK_TITLE_WORDS
)
