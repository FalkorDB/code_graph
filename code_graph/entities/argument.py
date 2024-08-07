from typing import Optional

class Argument:
    def __init__(self, name: str, type_: Optional[str]) -> None:
        """
        Initialize an Argument object.

        Args:
            name (str): Name of the argument.
            type_ (Optional[str], optional): Type of the argument. Defaults to None.
        """

        if type_ is None:
            type_ = 'Unknown'

        self.name = name
        self.type = type_

    def __str__(self) -> str:
        return f"""
            name:      {self.name}
            type_:     {self.type_}"""

    def __repr__(self) -> str:
        return f"""
            name:      {self.name}
            type:     {self.type}"""

    def __eq__(self, other) -> bool:
        if not isinstance(other, Argument):
            return False

        return self.name == other.name and self.type == other.type
