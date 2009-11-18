from pypy.module.oracle.test.test_connect import OracleTestBase

class AppTestStringVar(OracleTestBase):

    def test_rowid(self):
        cur = self.cnx.cursor()
        var = cur.var(oracle.NUMBER)
        cur.execute("select rowid from dual")
        rowid, = cur.fetchone()
        cur.execute("select * from dual where rowid = :r",
                    r=rowid)
        cur.fetchall()
        assert cur.rowcount == 1

    def test_array(self):
        cur = self.cnx.cursor()
        array = ["n%d" % d for d in range(20)]
        tablelen = cur.var(oracle.NUMBER)
        output = cur.var(oracle.STRING)
        statement = """
                declare
                  array dbms_utility.uncl_array := :array;
                begin
                  dbms_utility.table_to_comma(
                      array, :tablelen, :output);
                end;"""
        cur.execute(statement,
                    array=array,
                    tablelen=tablelen,
                    output=output)
        assert tablelen.getvalue() == 20
        assert output.getvalue() == ','.join(array)

    def test_array_bysize(self):
        cur = self.cnx.cursor()
        array = ["n%d" % d for d in range(20)]
        tablelen = cur.var(oracle.NUMBER)
        output = cur.var(oracle.STRING)
        cur.setinputsizes(array=[oracle.STRING, 10])
        statement = """
                declare
                  array dbms_utility.uncl_array := :array;
                begin
                  dbms_utility.table_to_comma(
                      array, :tablelen, :output);
                end;"""
        cur.execute(statement,
                    array=array,
                    tablelen=tablelen,
                    output=output)
        assert tablelen.getvalue() == 20
        assert output.getvalue() == ','.join(array)

    def test_arrayvar(self):
        cur = self.cnx.cursor()
        array = ["n%d" % d for d in range(20)]
        tablelen = cur.var(oracle.NUMBER)
        output = cur.var(oracle.STRING)
        arrayvar = cur.arrayvar(oracle.STRING, array)
        arrayvar.setvalue(0, array)
        statement = """
                declare
                  array dbms_utility.uncl_array := :array;
                begin
                  dbms_utility.table_to_comma(
                      array, :tablelen, :output);
                end;"""
        cur.execute(statement,
                    array=arrayvar,
                    tablelen=tablelen,
                    output=output)
        assert tablelen.getvalue() == 20
        assert output.getvalue() == ','.join(array)

    def test_arrayvar_out(self):
        cur = self.cnx.cursor()
        array = ["n%d" % d for d in range(20)]
        tablelen = cur.var(oracle.NUMBER)
        arrayvar = cur.arrayvar(oracle.STRING, 25)
        statement = """
                declare
                  array dbms_utility.uncl_array;
                begin
                  dbms_utility.comma_to_table(
                      :input, :tablelen, array);
                  :array := array;
                end;"""
        cur.execute(statement,
                    input=','.join(array),
                    tablelen=tablelen,
                    array=arrayvar)
        assert tablelen.getvalue() == 20
        # dbms_utility.comma_to_table returns a 'NULL-terminated' table
        assert arrayvar.getvalue() == array + [None]