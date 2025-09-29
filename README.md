# whatdidyoudo

A minimal Flask app that shows the amount of OpenStreetMap changes made by a user on a day.

## Background

I often ask myself after contributing many changes to [OpenStreetMap](https://www.openstreetmap.org/),
either by walking around while extensively using [StreetComplete](https://streetcomplete.app/),
[MapComplete](https://mapcomplete.org/) or [Vespucci](https://vespucci.io/), or by doing some tasks
in [iD](https://www.openstreetmap.org/edit) or [JOSM](https://josm.openstreetmap.de/):

***How many changes did I contribute to the map today?***

I'm not the only one. I heard questions like this quite a few times:

***Where can I see how much I did on yesterday's mapwalk?***

Because I think that simple questions deserve simple answers, I made this tool to give exactly
this information and nothing else.

You don't need to self-host it, it is available for anyone at
[whatdidyoudo.rompe.org](https://whatdidyoudo.rompe.org).

## Setup

Fun fact: of course you don't really need *uv* for this. I'm just using this project to
get used to it as I think it has a lot of potential.

### Install [uv](https://github.com/astral-sh/uv) if needed

```sh
pip install uv
```

### Install dependencies using *uv*

```sh
uv pip install -r pyproject.toml
```

If you want to develop:

```sh
uv pip install -r pyproject.toml --extra dev
```

### Run tests

```sh
pytest
```

### Run the app in test mode

```sh
python whatdidyoudo/app.py
```

Visit [http://127.0.0.1:5000/](http://127.0.0.1:5000/) in your browser to see "hello world".

### Build a package and upload it to Pypi

```sh
uvx hatchling build
uvx twine upload dist/*
```

## License

This project is licensed under the MIT License. See the `pyproject.toml` for details.
