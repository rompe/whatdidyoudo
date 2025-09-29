# whatdidyoudo

A minimal Flask app that prints "hello world" in the browser.

## Setup

1. Install [uv](https://github.com/astral-sh/uv) if needed:

   ```sh
   pip install uv
   ```

2. Install dependencies using *uv*:

   ```sh
   uv pip install -r pyproject.toml
   ```

   If you want to develop:

   ```sh
   uv pip install -r pyproject.toml --extra dev
   ```

3. Run the app in test mode:

   ```sh
   python run_test.py
   ```

   Visit [http://127.0.0.1:5000/](http://127.0.0.1:5000/) in your browser to see "hello world".
