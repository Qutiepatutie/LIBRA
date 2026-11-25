from django.test import SimpleTestCase

from library.recommender.dewey import DEWEY_DIVISIONS, subject_token
from library.recommender.preprocess import (
    author_tokens,
    clean_tags,
    clean_text,
    prepare,
    program_subjects,
    work_key,
)
from library.recommender.stopwords import STOP_WORDS


class CleanTextTests(SimpleTestCase):
    def test_placeholders_and_non_strings_are_empty(self):
        for value in (None, "", "  ", "None", "none.", "Unknown", " N/A ", 5, ["x"]):
            self.assertEqual(clean_text(value), "")

    def test_real_text_is_stripped(self):
        self.assertEqual(clean_text("  2nd edition "), "2nd edition")


class CleanTagsTests(SimpleTestCase):
    def test_drops_call_numbers_scripts_underscores_placeholders(self):
        tags = ["Compilers", "Qa76.76.c65 a37 2007", "Bm545 .d3312 2002", "005.4/53", "005.1",
                "Компьютеры", "open_syllabus_project", "None", "Programmation parallèle", "compilers"]
        self.assertEqual(clean_tags(tags), ["Compilers", "Programmation parallèle"])

    def test_control_character_cuts_the_tag(self):
        self.assertEqual(clean_tags(["Philosophy, Jewish.\u001e 0"]), ["Philosophy, Jewish."])

    def test_at_most_fifteen_tags(self):
        self.assertEqual(clean_tags([f"Subject {n}" for n in range(176)]), [f"Subject {n}" for n in range(15)])

    def test_non_list_values(self):
        self.assertEqual(clean_tags(None), [])
        self.assertEqual(clean_tags(5), [])
        self.assertEqual(clean_tags({"a": 1}), [])
        self.assertEqual(clean_tags("Programming"), ["Programming"])
        self.assertEqual(clean_tags(["Logic", None, 7, ["x"]]), ["Logic"])


class AuthorTokenTests(SimpleTestCase):
    def test_both_name_orders_give_one_token(self):
        self.assertEqual(author_tokens("Alfred V. Aho"), {"alfred_aho": "Alfred Aho"})
        self.assertEqual(author_tokens("Aho, Alfred V."), {"alfred_aho": "Alfred Aho"})

    def test_several_authors(self):
        self.assertEqual(list(author_tokens("Andy Hunt; Dave Thomas & Ana Cruz and Li Wei")),
                         ["andy_hunt", "dave_thomas", "ana_cruz", "li_wei"])

    def test_et_al_gives_no_token(self):
        self.assertEqual(author_tokens("Quilantang, et al."), {})

    def test_full_name_before_et_al_is_kept(self):
        self.assertEqual(author_tokens("Masaaki Mitani et al."), {"masaaki_mitani": "Masaaki Mitani"})

    def test_real_multi_author_formats(self):
        self.assertEqual(list(author_tokens("Clark, Alexander & Sousa, Bailey")), ["alexander_clark", "bailey_sousa"])
        self.assertEqual(list(author_tokens("Gopee, Niel and Galloway, Jo")), ["niel_gopee", "jo_galloway"])
        self.assertEqual(list(author_tokens("Brinkmann, Svend,")), ["svend_brinkmann"])

    def test_credentials_after_second_comma_ignored(self):
        self.assertEqual(list(author_tokens("Daluyong, Mirasol T. Abrenica, MD, FPCP")), ["mirasol_abrenica_daluyong"])

    def test_accents_and_missing_author(self):
        self.assertEqual(list(author_tokens("Peña, José")), ["jose_pena"])
        for value in (None, "", "Unknown"):
            self.assertEqual(author_tokens(value), {})


class WorkKeyTests(SimpleTestCase):
    def test_editions_share_a_key(self):
        self.assertEqual(work_key("Calculus, 11th ed.", "James Stewart"),
                         work_key("Calculus (10th edition)", "Stewart, James"))
        self.assertEqual(work_key("Compilers", "Alfred V. Aho")[0], "compilers")

    def test_different_authors_are_different_works(self):
        self.assertNotEqual(work_key("Psychology", "Robert A. Baron"), work_key("Psychology", "David Myers"))


class ProgramSubjectTests(SimpleTestCase):
    def test_real_sample_spellings(self):
        cases = {
            "Master of Arts in Education, Major in Educational Management": ["Education", "Educational Management"],
            "Master in Public Administration Non-Thesis Track": ["Public Administration"],
            "Master in Infromation of Technology": ["Information Technology"],
            "Masrer of Science in Hospitality Management": ["Hospitality Management"],
            "Master in Business in Administration": ["Business Administration"],
            "Doctor of philosophy in Nursing, Major in Nursing Administration": ["Nursing", "Nursing Administration"],
            "Master of Science in Criminal Justice with Specialization in Criminology": ["Criminal Justice", "Criminology"],
            "Major in Educational Management": ["Educational Management"],
            "Antas Pagkadalubhasa sa Sining ng Pagtuturo, Medyor sa Filipino":
                ["Antas Pagkadalubhasa sa Sining ng Pagtuturo", "Filipino"],
            "Bachelor of Science in Pharmacy": ["Pharmacy"],
            "": [],
        }
        for raw, expected in cases.items():
            self.assertEqual(program_subjects(raw), expected, raw)


class SubjectTokenTests(SimpleTestCase):
    def test_real_call_numbers(self):
        cases = {
            "001.4 K96 2019": ("ddc_000", "Computer science, knowledge & systems"),
            "F 346.59902 D71 2023": ("ddc_340", "Law"),
            "MT 362.11 V82 2020": ("ddc_360", DEWEY_DIVISIONS["360"]),
            "D 658 A2 2021": ("ddc_650", "Management & public relations"),
            "TH 615 P43t 2023": ("ddc_610", "Medicine & health"),
            "FR 150 A1 2020": ("ddc_150", "Psychology"),
            "FIC D64 2001 bk.1": ("ddc_fic", "Fiction"),
            "RIZ B41 2016": ("ddc_riz", "Rizaliana"),
            "FB A2 2016": ("ddc_bio", "Biography"),
            "B G85 2007": ("ddc_bio", "Biography"),
        }
        for call, expected in cases.items():
            self.assertEqual(subject_token(call), expected, call)

    def test_no_subject(self):
        for call in ("", None, 5, "X 12 A1", "00"):
            self.assertIsNone(subject_token(call))

    def test_all_hundred_divisions_are_named(self):
        self.assertEqual(sorted(DEWEY_DIVISIONS), [f"{n:03d}" for n in range(0, 1000, 10)])
        self.assertTrue(all(name.strip() for name in DEWEY_DIVISIONS.values()))


class PrepareTests(SimpleTestCase):
    def test_document_text_and_labels(self):
        doc = prepare("Compilers, 2nd ed.", "Aho, Alfred V.", ["Compilers", "005.4/53"], "Parsing and code generation",
                      "005.453 A28 2007")
        self.assertEqual(doc.text, "Compilers alfred_aho Compilers ddc_000 Parsing and code generation")
        self.assertEqual(doc.labels, {"alfred_aho": "Alfred Aho", "ddc_000": "Computer science, knowledge & systems"})
        self.assertEqual(doc.description_length, len("Parsing and code generation"))

    def test_empty_fields_add_nothing(self):
        doc = prepare("Body Language", None, None, "None")
        self.assertEqual(doc.text, "Body Language")
        self.assertEqual(doc.description_length, 0)


class StopWordTests(SimpleTestCase):
    def test_lists_are_combined(self):
        for word in ("the", "study", "ng", "evaluation", "pampanga", "introduction", "applied"):
            self.assertIn(word, STOP_WORDS)
        self.assertNotIn("feasibility", STOP_WORDS)
        self.assertEqual(STOP_WORDS, sorted(set(STOP_WORDS)))
