from typing import Optional

class Class():
    """
    Represents a class with a name and an optional docstring.
    """

    def __init__(self, path: str, name: str, doc: Optional[str],
                 src_start: int, src_end: int) -> None:
        """
        Initializes a Class instance.

        Args:
            path (str): The path under which the class is defined
            name (str): The name of the class.
            doc (Optional[str], optional): The docstring of the class. Defaults to None.
            src_start (int): Start line of the class in the source code.
            src_end (int): End line of the class in the source code.
        """

        self.path      = path
        self.name      = name
        self.doc       = doc
        self.src_start = src_start
        self.src_end   = src_end

    def __str__(self) -> str:
        return f"""
            id:        {self.id if hasattr(self, 'id') else 'Unknown'}
            path:      {self.path}
            name:      {self.name}
            doc:       {self.doc}
            src_start: {self. src_start}
            src_end:   {self.src_end}"""

    def __eq__(self, other):
        if not isinstance(other, Class):
            return False

        return (self.path      == other.path      and
                self.name      == other.name      and
                self.doc       == other.doc       and
                self.src_start == other.src_start and
                self.src_end   == other.src_end)

