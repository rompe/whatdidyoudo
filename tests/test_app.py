"""Unit tests for the WhatDidYouDo Flask application."""
import unittest
from whatdidyoudo.app import app


class WhatDidYouDoTestCase(unittest.TestCase):
    """Unit tests for the WhatDidYouDo Flask application."""
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True  # type: ignore

    def test_home_status_code(self):
        """Test that the home page returns a 200 status code."""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)

    def test_form_contains_user_and_date(self):
        """Test that the form contains fields for user and date."""
        response = self.app.get('/')
        html = response.get_data(as_text=True)
        self.assertIn('name="user"', html)
        self.assertIn('name="date"', html)

    def test_user_date_route(self):
        """Test that the user/date route returns a 200 status code."""
        response = self.app.get('/rompe/2024-09-29')
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('rompe', html)
        self.assertIn('2024-09-29', html)


if __name__ == '__main__':
    unittest.main()
