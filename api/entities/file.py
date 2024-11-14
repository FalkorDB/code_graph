class File:
    """
    Represents a file with basic properties like path, name, and extension.
    """

    def __init__(self, path: str, name: str, ext: str) -> None:
        """
        Initialize a File object.

        Args:
            path (str): The full path to the file.
            name (str): The name of the file.
            ext (str): The file extension.
        """

        self.path = path
        self.name = name
        self.ext = ext

    def __str__(self) -> str:
        return f"""
            path:      {self.path}
            name:      {self.name}
            ext:       {self.ext}"""

    def __eq__(self, other) -> bool:
        if not isinstance(other, File):
            return False

        return (self.ext  == other.ext   and
                self.path == other.path  and
                self.name == other.name)

