import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "openrouter_benchmark.py"
SPEC = importlib.util.spec_from_file_location("openrouter_benchmark", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PromptPrefixTests(unittest.TestCase):
    def test_compose_user_question_without_prefix_returns_original_question(self) -> None:
        question = "Can you estimate the tensile strength of our sprint backlog?"
        result = MODULE.compose_user_question(question, "")
        self.assertEqual(result, question)

    def test_compose_user_question_prepends_prefix_with_blank_line(self) -> None:
        result = MODULE.compose_user_question(
            "What's the resonance frequency of this setup?",
            "A third party asked the following question.",
        )

        self.assertEqual(
            result,
            "A third party asked the following question.\n\n"
            "What's the resonance frequency of this setup?",
        )


if __name__ == "__main__":
    unittest.main()
