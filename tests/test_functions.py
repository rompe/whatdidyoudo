"""Unit tests for the some utility functions."""
import unittest
import whatdidyoudo.app


class WhatDidYouDoFunctionsTestCase(unittest.TestCase):
    """Unit tests for the some utility functions."""
    def test_get_changesets(self) -> None:
        """Test get_changesets."""
        changesets, message = whatdidyoudo.app.get_changesets(
            user="rompe", start_date="2025-10-31T00:00",
            end_date="2026-01-02T23:59")
        self.assertFalse(message)
        self.assertEqual(len(changesets), 166)

    def test_get_changes(self) -> None:
        """Test get_changesets."""
        changes, changeset_ids, message = whatdidyoudo.app.get_changes(
            user="rompe", start_date="2026-01-02T00:00",
            end_date="2026-01-02T23:59")
        self.assertFalse(message)
        self.assertEqual(len(changes), 1)
        self.assertTrue("StreetComplete 62.1" in changes)
        change = changes["StreetComplete 62.1"]
        self.assertEqual(change.changesets, 1)
        self.assertEqual(change.changes, 1)
        self.assertEqual(len(changeset_ids), 1)
