from textutils import slugify


class Post:
    def __init__(self, title: str):
        self.title = title

    @property
    def slug(self) -> str:
        return slugify(self.title, separator="_")
