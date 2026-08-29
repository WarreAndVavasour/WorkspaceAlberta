import stat
import tempfile
import unittest
from pathlib import Path

from scripts.configure_e2b import (
    next_steps,
    update_env_text,
    validate_e2b_key,
    write_secret_env,
)


class ConfigureE2BTest(unittest.TestCase):
    def test_update_env_text_preserves_other_settings_and_replaces_key(self) -> None:
        original = "OTHER=value\nE2B_API_KEY=old\nLAST=setting\n"
        updated = update_env_text(original, "e2b_new-secret")
        self.assertEqual(
            updated,
            "OTHER=value\nE2B_API_KEY=e2b_new-secret\nLAST=setting\n",
        )
        self.assertEqual(updated.count("E2B_API_KEY="), 1)

    def test_write_secret_env_creates_owner_only_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            write_secret_env(path, "e2b_secret-value")
            self.assertEqual(path.read_text(), "E2B_API_KEY=e2b_secret-value\n")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_next_steps_use_project_venv_and_install_dependencies(self) -> None:
        instructions = next_steps()
        self.assertIn("uv pip install --python .venv/bin/python -r requirements.txt", instructions)
        self.assertIn(".venv/bin/python scripts/e2b_bid_room_smoke.py", instructions)
        self.assertNotIn("Run: python ", instructions)

    def test_validate_e2b_key_rejects_unsafe_or_unexpected_values(self) -> None:
        for value in ("", "not-an-e2b-key", "e2b_bad\nINJECTED=yes"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_e2b_key(value)
        self.assertEqual(validate_e2b_key(" e2b_valid-value "), "e2b_valid-value")


if __name__ == "__main__":
    unittest.main()
