# This module was taken from https://github.com/devnull255/sqlite-shelve/
#
# Copyright (c) 2020 Michael D. Mabin and other contributors
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import pickle
import sqlite3
import os


class Shelf:
    """An SQLite implementation of the Python Shelf interface

    """
    def __init__(self, fname, mode):
        """Open or create an existing sqlite3_shelf

        """
        if mode == 'r':
            if not os.access(fname, os.R_OK):
                raise OSError(f'Cannot read {fname}')
            fname += '?mode=ro'
            self.readonly = True
        elif mode in 'cw':
            if not os.access(fname, os.F_OK):
                if not os.access(os.path.dirname(fname), os.W_OK):
                    raise OSError(f'Cannot create {fname}')
            elif not os.access(fname, os.W_OK):
                raise OSError(f'Cannot write {fname}')
            self.readonly = False
        else:
            raise ValueError(f'Illegal mode {mode}')

        self.db = sqlite3.connect('file:' + fname, uri=True,
                                  isolation_level=None)
        # create shelf table if it doesn't already exist
        cursor = self.db.cursor()
        try:
            cursor.execute("select * from sqlite_master"
                           " where type = 'table' and tbl_name = 'shelf'")
            rows = cursor.fetchall()
            if len(rows) == 0:
                if self.readonly:
                    raise OSError(f'No table "shelf" in {fname}')
                cursor.execute("create table shelf"
                               " (id integer primary key autoincrement,"
                               " key_str text,"
                               " value_str text,"
                               " unique(key_str))")
        finally:
            cursor.close()

    def __setitem__(self, key, value):
        """Set an entry for key to value using pickling

        """
        if self.readonly:
            raise OSError("Readonly database")
        pdata = pickle.dumps(value, pickle.HIGHEST_PROTOCOL)
        cursor = self.db.cursor()
        try:
            cursor.execute("insert or replace into shelf (key_str, value_str)"
                           " values (:key,:value)",
                           {'key': key, 'value': sqlite3.Binary(pdata)})
            self.db.commit()
        finally:
            cursor.close()

    def get(self, key, default_value=None):
        """Return an entry for key

        """
        try:
            return self[key]
        except KeyError:
            return default_value

    def __getitem__(self, key):
        """Returns an entry for key

        """
        cursor = self.db.cursor()
        try:
            cursor.execute("select value_str from shelf"
                           " where key_str = :key",
                           {'key': key})
            result = cursor.fetchone()
            if result:
                return pickle.loads(result[0])
            else:
                raise KeyError(key)
        finally:
            cursor.close()

    def keys(self):
        """Return list of keys

        """
        cursor = self.db.cursor()
        try:
            cursor.execute('select key_str from shelf')
            for row in cursor:
                yield row[0]
        finally:
            cursor.close()

    def values(self):
        """Return list of keys

        """
        cursor = self.db.cursor()
        try:
            cursor.execute('select value_str from shelf')
            for row in cursor:
                yield pickle.loads(row[0])
        finally:
            cursor.close()

    def items(self):
        """Return list of keys

        """
        cursor = self.db.cursor()
        try:
            cursor.execute('select key_str, value_str from shelf')
            for row in cursor:
                yield row[0], pickle.loads(row[1])
        finally:
            cursor.close()

    def __contains__(self, key):
        """implements in operator if <key> in db

        """
        return key in self.keys()

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        """ Returns number of entries in shelf """
        cursor = self.db.cursor()
        try:
            cursor.execute('select count(*) from shelf')
            row = cursor.fetchone()
            return row[0]
        finally:
            cursor.close()

    def __delitem__(self, key):
        """Delete an existing item.

        """
        if self.readonly:
            raise OSError("Readonly database")
        cursor = self.db.cursor()
        try:
            cursor.execute("delete from shelf where key_str = :key",
                           {'key': key})
        finally:
            cursor.close()

    def close(self):
        """Close database and commits changes

        """
        self.db.commit()
        self.db.close()


def open(dbpath, mode):
    """Create and return a Shelf object

    """
    return Shelf(dbpath + '.sqlite3', mode)


def close(db):
    """Commit changes to the database

    """
    db.close()
