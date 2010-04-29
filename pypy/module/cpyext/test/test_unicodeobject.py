# encoding: iso-8859-15
from pypy.module.cpyext.test.test_api import BaseApiTest
from pypy.module.cpyext.unicodeobject import Py_UNICODE
from pypy.rpython.lltypesystem import rffi, lltype
import sys, py

class TestUnicode(BaseApiTest):
    def test_unicodeobject(self, space, api):
        assert api.PyUnicode_GET_SIZE(space.wrap(u'sp�m')) == 4
        assert api.PyUnicode_GetSize(space.wrap(u'sp�m')) == 4
        unichar = rffi.sizeof(Py_UNICODE)
        assert api.PyUnicode_GET_DATA_SIZE(space.wrap(u'sp�m')) == 4 * unichar

        encoding = rffi.charp2str(api.PyUnicode_GetDefaultEncoding())
        w_default_encoding = space.call_function(
            space.sys.get('getdefaultencoding')
        )
        assert encoding == space.unwrap(w_default_encoding)
        invalid = rffi.str2charp('invalid')
        utf_8 = rffi.str2charp('utf-8')
        prev_encoding = rffi.str2charp(space.unwrap(w_default_encoding))
        assert api.PyUnicode_SetDefaultEncoding(invalid) == -1
        assert api.PyErr_Occurred() is space.w_LookupError
        api.PyErr_Clear()
        assert api.PyUnicode_SetDefaultEncoding(utf_8) == 0
        assert rffi.charp2str(api.PyUnicode_GetDefaultEncoding()) == 'utf-8'
        assert api.PyUnicode_SetDefaultEncoding(prev_encoding) == 0
        rffi.free_charp(invalid)
        rffi.free_charp(utf_8)
        rffi.free_charp(prev_encoding)

    def test_AS(self, space, api):
        word = space.wrap(u'spam')
        array = rffi.cast(rffi.CWCHARP, api.PyUnicode_AS_DATA(word))
        array2 = api.PyUnicode_AS_UNICODE(word)
        array3 = api.PyUnicode_AsUnicode(word)
        for (i, char) in enumerate(space.unwrap(word)):
            assert array[i] == char
            assert array2[i] == char
            assert array3[i] == char
        self.raises(space, api, TypeError, api.PyUnicode_AsUnicode,
                    space.wrap('spam'))

        utf_8 = rffi.str2charp('utf-8')
        encoded = api.PyUnicode_AsEncodedString(space.wrap(u'sp�m'),
                                                utf_8, None)
        assert space.unwrap(encoded) == 'sp\xc3\xa4m'
        self.raises(space, api, TypeError, api.PyUnicode_AsEncodedString,
               space.newtuple([1, 2, 3]), None, None)
        self.raises(space, api, TypeError, api.PyUnicode_AsEncodedString,
               space.wrap(''), None, None)
        rffi.free_charp(utf_8)

        buf = rffi.unicode2wcharp(u"12345")
        api.PyUnicode_AsWideChar(space.wrap(u'longword'), buf, 5)
        assert rffi.wcharp2unicode(buf) == 'longw'
        api.PyUnicode_AsWideChar(space.wrap(u'a'), buf, 5)
        assert rffi.wcharp2unicode(buf) == 'a'
        rffi.free_wcharp(buf)

    def test_IS(self, space, api):
        for char in [0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x1c, 0x1d, 0x1e, 0x1f,
                     0x20, 0x85, 0xa0, 0x1680, 0x2000, 0x2001, 0x2002,
                     0x2003, 0x2004, 0x2005, 0x2006, 0x2007, 0x2008,
                     0x2009, 0x200a,
                     #0x200b is in Other_Default_Ignorable_Code_Point in 4.1.0
                     0x2028, 0x2029, 0x202f, 0x205f, 0x3000]:
            assert api.Py_UNICODE_ISSPACE(unichr(char))
        assert not api.Py_UNICODE_ISSPACE(u'a')

        assert api.Py_UNICODE_ISDECIMAL(u'\u0660')
        assert not api.Py_UNICODE_ISDECIMAL(u'a')

        for char in [0x0a, 0x0d, 0x1c, 0x1d, 0x1e, 0x85, 0x2028, 0x2029]:
            assert api.Py_UNICODE_ISLINEBREAK(unichr(char))

        assert api.Py_UNICODE_ISLOWER(u'�')
        assert not api.Py_UNICODE_ISUPPER(u'�')
        assert api.Py_UNICODE_ISLOWER(u'a')
        assert not api.Py_UNICODE_ISUPPER(u'a')
        assert not api.Py_UNICODE_ISLOWER(u'�')
        assert api.Py_UNICODE_ISUPPER(u'�')

    def test_TOLOWER(self, space, api):
        assert api.Py_UNICODE_TOLOWER(u'�') == u'�'
        assert api.Py_UNICODE_TOLOWER(u'�') == u'�'

    def test_TOUPPER(self, space, api):
        assert api.Py_UNICODE_TOUPPER(u'�') == u'�'
        assert api.Py_UNICODE_TOUPPER(u'�') == u'�'

    def test_decode(self, space, api):
        b_text = rffi.str2charp('caf\x82xx')
        b_encoding = rffi.str2charp('cp437')
        assert space.unwrap(
            api.PyUnicode_Decode(b_text, 4, b_encoding, None)) == u'caf\xe9'

        w_text = api.PyUnicode_FromEncodedObject(space.wrap("test"), b_encoding, None)
        assert space.is_true(space.isinstance(w_text, space.w_unicode))
        assert space.unwrap(w_text) == "test"

        assert api.PyUnicode_FromEncodedObject(space.wrap(u"test"), b_encoding, None) is None
        assert api.PyErr_Occurred() is space.w_TypeError
        assert api.PyUnicode_FromEncodedObject(space.wrap(1), b_encoding, None) is None
        assert api.PyErr_Occurred() is space.w_TypeError
        api.PyErr_Clear()

        rffi.free_charp(b_text)
        rffi.free_charp(b_encoding)

    def test_leak(self):
        py.test.skip("This test seems to leak memory")
        size = 50
        raw_buf, gc_buf = rffi.alloc_buffer(size)
        for i in range(size): raw_buf[i] = 'a'
        str = rffi.str_from_buffer(raw_buf, gc_buf, size, size)
        rffi.keep_buffer_alive_until_here(raw_buf, gc_buf)

    def test_mbcs(self, space, api):
        if sys.platform != 'win32':
            py.test.skip("mcbs encoding only exists on Windows")
        # unfortunately, mbcs is locale-dependent.
        # This tests works at least on a Western Windows.
        unichars = u"abc" + unichr(12345)
        wbuf = rffi.unicode2wcharp(unichars)
        w_str = api.PyUnicode_EncodeMBCS(wbuf, 4, None)
        rffi.free_wcharp(wbuf)
        assert space.type(w_str) is space.w_str
        assert space.str_w(w_str) == "abc?"

        # XXX this test seems to leak references, see test_leak above
        from pypy.module.cpyext.test.test_cpyext import freeze_refcnts
        freeze_refcnts(self)