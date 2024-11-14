from .argument import Argument
from typing import List, Optional

class Function:
    def __init__(self, path: str, name: str, doc: Optional[str],
                 ret_type: Optional[str], src: Optional[str],
                 src_start: int, src_end: int) -> None:
        """
        Initialize a Function object.

        Args:
            path (str): Path of the function definition.
            name (str): Name of the function.
            ret_type (Optional[str]): Return type of the function.
            src_start (int): Start line of the function in the source code.
            src_end (int): End line of the function in the source code.
        """

        self.path      = path
        self.name      = name
        self.doc       = doc
        self.ret_type  = ret_type
        self.src       = src
        self.src_start = src_start
        self.src_end   = src_end

        self.args: List[Argument] = []

    def __str__(self) -> str:
        return f"""
            path:      {self.path}
            name:      {self.name}
            doc:       {self.doc}
            ret_type:  {self.ret_type}
            src:       {self.src}
            src_start: {self. src_start}
            src_end:   {self.src_end}
            args:      {self.args}"""

    def __eq__(self, other):
        if not isinstance(other, Function):
            return False

        return (self.doc       == other.doc        and
                self.args      == other.args       and
                self.path      == other.path       and
                self.name      == other.name       and
                self.ret_type  == other.ret_type   and
                self.src_end   == other.src_end    and
                self.src_start == other.src_start)

    def add_argument(self, name: str, t: Optional[str]) -> None:
        """
        Add an argument to the function.

        Args:
            name (str): Name of the argument.
            type_ (str): Type of the argument.
        """

        self.args.append(Argument(name, t))

