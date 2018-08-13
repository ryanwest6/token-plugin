from typing import NamedTuple, Set, Optional

Output = NamedTuple('Output', [('address', str), ('seq_no', int),
                               ('value', Optional[int])])


def less_than(self, other):
    return self.seq_no < other.seq_no

# This is added to make this sortable by python's heap implementation
Output.__lt__ = less_than


OutputList = NamedTuple("OutputList",
                        [("spent", Set[int]), ("unspent", Set[int])])
