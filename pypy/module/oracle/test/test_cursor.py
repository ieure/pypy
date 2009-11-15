from pypy.conftest import gettestobjspace
import py

from pypy.rpython.tool.rffi_platform import CompilationError
try:
    from pypy.module.oracle import roci
except (CompilationError, ImportError):
    py.test.skip("Oracle client not available")

class AppTestCursor:

    def setup_class(cls):
        space = gettestobjspace(usemodules=('oracle',))
        cls.space = space
        space.setitem(space.builtin.w_dict, space.wrap('oracle'),
                      space.getbuiltinmodule('cx_Oracle'))
        cls.w_username = space.wrap('cx_oracle')
        cls.w_password = space.wrap('dev')
        cls.w_tnsentry = space.wrap('')
        cls.w_cnx = space.appexec(
            [cls.w_username, cls.w_password, cls.w_tnsentry],
            """(username, password, tnsentry):
                import cx_Oracle
                return cx_Oracle.connect(username, password, tnsentry)
            """)

    def test_bindNames(self):
        cur = self.cnx.cursor()
        raises(oracle.ProgrammingError, cur.bindnames)
        cur.prepare("begin null; end;")
        assert cur.bindnames() == []
        cur.prepare("begin :retval := :inval + 5; end;")
        assert cur.bindnames() == ["RETVAL", "INVAL"]
        cur.prepare("begin :retval := :a * :a + :b * :b; end;")
        assert cur.bindnames() == ["RETVAL", "A", "B"]
        cur.prepare("begin :a := :b + :c + :d + :e + :f + :g + "
                    ":h + :i + :j + :k + :l; end;")
        assert cur.bindnames() == ["A", "B", "C", "D", "E", "F",
                                   "G", "H", "I", "J", "K", "L"]

    def test_bind_out(self):
        cur = self.cnx.cursor()
        var = cur.var(oracle.NUMBER)
        var.setValue(0, 5)
        assert var.getValue(0) == 5
        assert var.getValue() == 5
        cur.execute("begin :1 := 3; end;", (var,))
        value = var.getValue(0)
        assert value == 3
        assert isinstance(value, float)

    def test_callFunc0(self):
        cur = self.cnx.cursor()
        try:
            cur.execute("drop function pypy_temp_function")
        except oracle.DatabaseError:
            pass
        cur.execute("create function pypy_temp_function "
                    "return number as "
                    "begin return 42; end;")
        assert cur.callfunc("pypy_temp_function",
                            oracle.NUMBER) == 42
        
    def test_callFunc1(self):
        cur = self.cnx.cursor()
        try:
            cur.execute("drop function pypy_temp_function")
        except oracle.DatabaseError:
            pass
        cur.execute("create function pypy_temp_function "
                    "(x varchar2, y number) return number as "
                    "begin return length(x) + y; end;")
        res = cur.callfunc("pypy_temp_function",
                            oracle.NUMBER, ("Hi", 5))
        assert res == 7

