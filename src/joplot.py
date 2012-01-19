#! /usr/bin/env python
#
"""
A CGI application for plotting the PBS accounting data.
"""
__docformat__ = 'reStructuredText'

from math import log
import cgi
import datetime
import itertools
import sys

# for debugging
import cgitb; cgitb.enable(display=1, logdir="/tmp")

# DB connectivity
import MySQLdb as sql

# configuration
from ConfigParser import SafeConfigParser


# utlity classes
class DateRange(object):
    """Iterate over a range of dates.
    Note that, contrary to common Python usage, the ending date
    is *included* in the returned range.

    From/to dates must be given as ISO format YYYY-MM-DD strings::

    >>> for date in DateRange('2009-02-02', '2009-02-03'): print date
    2009-02-02
    2009-02-03
    
    """

    MONTH_END = ["There's no month 0!", 
              #  Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec
                 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    
    def __init__(self, start, end, step='daily'):
        #: starting date
        self.y1, self.m1, self.d1 = [int(x) for x in start.split('-')]

        #: ending date
        if end != None:
            self.y2, self.m2, self.d2 = [int(x) for x in end.split('-')]
        else:
            self.y2, self.m2, self.d2 = self.y1, self.m1, self.d1

        #: current date
        self.d, self.m, self.y = None, None, None

        #: stepping of the iteration
        self.step = step
        # see implementation of next()
        if step in ['monthly', 'yearly']:
            self.d1 = None
            self.d2 = None
        if step == 'yearly':
            self.m1 = None
            self.m2 = None

    def __iter__(self):
        return self

    def next(self):
        if self.y is None:
            # return first date in range
            self.d = self.d1
            self.m = self.m1
            self.y = self.y1
        else:
            # stop iteration if 'to' date has been reached
            if (self.d, self.m, self.y) == (self.d2, self.m2, self.y2):
                raise StopIteration
            # advance month and year if needed
            if self.d: # daily
                if self.d == DateRange.MONTH_END[self.m]:
                    if self.m == 12:
                        self.y +=1
                        self.m = 1
                    else:
                        self.m += 1
                    self.d = 1
                else:
                    self.d += 1
            elif self.m: # monthly
                if self.m == 12:
                    self.y += 1
                    self.m = 1
                else:
                    self.m += 1
            else: # yearly
                self.y += 1
        if self.d: # daily
            return datetime.date(self.y, self.m, self.d)
        elif self.m: # monthly
            return '%04d-%02d' % (self.y, self.m)
        else: # yearly
            return '%04d' % self.y

## main

# get configuration options
config = SafeConfigParser()
config.read('pbsplots.ini')
db_db = config.get('database', 'db')
db_user = config.get('database', 'user')
db_host = config.get('database', 'host')
db_passwd = config.get('database', 'password')

# template defaults
class DictWithEmptyStringDefault(dict):
    """Like a standard 'dict', but returns the empty string
    when looking up a key that has not been defined yet."""
    def __getitem__(self, key):
        if self.has_key(key):
            return dict.__getitem__(self, key)
        else:
            return ''
values = DictWithEmptyStringDefault([
        ('content', 'Select plot characteristics above and click the "plot" button.')
        ])
IS_CHECKED = 'checked="checked"' # HTML ...*sigh*
IS_SELECTED = 'selected="selected"' 

print "Content-type: text/html"
print
form = cgi.FieldStorage()
if not form.has_key('y'):
    blank_form = open('pbsplots.template.html', 'r')
    print blank_form.read() % values
    sys.exit(0)

# what shall we SELECT for?
y = {
    'jobs':'COUNT(jobid)',
    'walltime':'SUM(used_walltime)',
    'cputime':'SUM(used_cputime)',
    }[form.getvalue('y')]
values["y_"+form.getvalue('y')+"_checked"] = IS_CHECKED

y_legend = {
    'jobs':'Number of jobs',
    'walltime':'Consumed wall-clock time (in seconds)',
    'cputime':'Consumed CPU time (in seconds)',
    }[form.getvalue('y')]


vo_roles = { # FIXME: this should be gotten by a DB query?
    'atlas': ['production', 'pilot', 'NULL'],
    'cms': [ 'production', 'priorityuser', 'NULL'],
    'lhcb': [ 'production', 'NULL' ],
    }

scopes = []
if form.has_key('total'):
    scopes.append(('Tier-2 total', ''))
    values['totals_checked'] = IS_CHECKED
for vo in ['atlas', 'cms', 'lhcb']:
    if form.has_key(vo):
        scopes.append((vo, 'AND vo="%s"' % vo))
        values[vo+'_checked'] = IS_CHECKED
        for role in vo_roles[vo]:
            if form.has_key('vo_'+vo+'_'+role):
                scopes.append(("%s/Role=%s" % (vo, role),
                               'AND vo="%s" AND role="%s"' % (vo, role)))
                values['vo_'+vo+'_'+role+'_checked'] = IS_CHECKED
n = len(scopes)

if 'range_of_days' == form.getvalue('timescale'):
    timescale='daily'
    date1, date2 = form.getvalue('from'), form.getvalue('to')
    values['range_of_days_checked'] = IS_CHECKED
    values['from_value'] = 'value="' + form.getvalue('from') + '"'
    values['to_value'] = 'value="' + form.getvalue('to') + '"'
elif 'single_day' == form.getvalue('timescale'):
    timescale='daily'
    date1, date2 = form.getvalue('date'), None
    values['single_day_checked'] = IS_CHECKED
    values['date_value'] = 'value="' + form.getvalue('date') + '"'
elif 'range_of_months' == form.getvalue('timescale'):
    timescale='monthly'
    date1 = '%s-%s-01' % (form.getvalue('monthly_from_year'), form.getvalue('monthly_from_month'))
    date2 = '%s-%s-%s' % (form.getvalue('monthly_to_year'), form.getvalue('monthly_to_month'), 
                              DateRange.MONTH_END[int(form.getvalue('monthly_to_month'))])
    values['range_of_months_checked'] = IS_CHECKED
    values['month_'+form.getvalue('monthly_from_month')+'_selected'] = IS_SELECTED
    values['year_'+form.getvalue('monthly_from_year')+'_selected'] = IS_SELECTED
    values['to_month_'+form.getvalue('monthly_to_month')+'_selected'] = IS_SELECTED
    values['to_year_'+form.getvalue('monthly_to_year')+'_selected'] = IS_SELECTED
elif 'single_month' == form.getvalue('timescale'):
    timescale='monthly'
    date1 = '%s-%s-01' % (form.getvalue('monthly_year'), form.getvalue('monthly_month'))
    date2 = '%s-%s-%s' % (form.getvalue('monthly_year'), form.getvalue('monthly_month'), 
                          DateRange.MONTH_END[int(form.getvalue('monthly_month'))])
    values['single_month_checked'] = IS_CHECKED
    values['month_'+form.getvalue('monthly_month')+'_selected'] = IS_SELECTED
    values['year_'+form.getvalue('monthly_year')+'_selected'] = IS_SELECTED
elif 'range_of_years' == form.getvalue('timescale'):
    timescale='yearly'
    date1 = '%s-01-01' % form.getvalue('yearly_from_year')
    date2 = '%s-12-31' % form.getvalue('yearly_to_year')
    values['range_of_years_checked'] = IS_CHECKED
    values['year_'+form.getvalue('yearly_from_year')+'_selected'] = IS_SELECTED
    values['to_year_'+form.getvalue('yearly_to_year')+'_selected'] = IS_SELECTED
elif 'single_year' == form.getvalue('timescale'):
    timescale='yearly'
    date1 = '%s-01-01' % form.getvalue('yearly_year')
    date2 = '%s-12-31' % form.getvalue('yearly_year')
    values['single_year_checked'] = IS_CHECKED
    values['year_'+form.getvalue('yearly_year')+'_selected'] = IS_SELECTED
else:
    raise ValueError('unknown value "%s" in "timescale" field' % form.getvalue('timescale'))


# connect to the database
mysql = sql.connect(host=db_host, user=db_user, 
                    passwd=db_passwd, db=db_db)
db = mysql.cursor()

results = []
for scope in scopes:
    if date2 != None:
        query = "SELECT date,%s FROM accounting WHERE date>='%s' and date<='%s' %s GROUP BY date ORDER BY date" \
            % (y, date1, date2, scope[1])
    else:
        query = "SELECT date,%s FROM accounting WHERE date='%s' %s GROUP BY date ORDER BY date" \
            % (y, date1, scope[1])
    try:
        db.execute(query)
    except sql.ProgrammingError, x:
        raise RuntimeError("Failed SQL query: %s: MySQL said: %s" % (query, x))
    results.append(dict(db.fetchall()))

db.close()
mysql.close()


# post-process data for generating graph:
if timescale == 'daily':
    data = [ ([ date ] + [ results[i].get(date, 0) for i in range(n) ])
             for date in DateRange(date1, date2) ]
else: # monthly or yearly
    data = [ ([ period ] + [ sum([ results[i][date] 
                                   for date in [ day for day in results[i].iterkeys() 
                                                 if day.isoformat().startswith(period) ] ])
                             for i in range(n) ])
             for period in DateRange(date1, date2, timescale) ]


# incantation for drawing chart with Google API
def chart_url(data, axes=None, title=None,
              colors=( # number of colors must match max number of data sets
                  '000000', # black
                  'cd0000', # red3
                  '00cd00', # green3
                  'cdcd00', # yellow3
                  '0000ee', # blue2
                  'cd00cd', # magenta3
                  '00cdcd', # cyan3
                  'e5e5e5', # gray90
                  '7f7f7f', # gray50
                  'ff0000', # red
                  '00ff00', # green
                  'ffff00', # yellow
                  'ff00ff', # magenta
                  '00ffff', # cyan
                  '262626', # gray15
                  )
              ):
    """Return URL for the Google graph depicting `data`."""
    xs = len(data)
    if xs == 1:
        cht = 'bvg&chbh=75,25,50' # vertical bar chart (alter default width of the bars)
    else:
        cht = 'lc' # line chart
    # need the max value to scale the graph
    # (the funny '[1,1]+..' thingy prevents Python "Iteration over non-sequence"
    # error when there are less than 2 values -- and ensures M>0)
    M = max(* [1,1] + [ max(* [1,1] + row[1:]) for row in data ])
    # dataset min/max values; all datasets must be pictured on the same scale
    chds = str.join(",", [("0,%d" % M)] * n)
    # dataset values; each dataset is a comma-separated list, and
    # different datasets are separated with a "|" character
    chd = str.join("|",
                   [ str.join(",", [("%d" % row[i]) for row in data])
                     for i in range(1,n+1) ])
    # place 8 ticks on y-axis at "powers of 10" interval
    chxr = 10**int(log( M/8.0) / log(10) + .5)
    # place 10 ticks on x-axis
    if xs <= 10:
        chxl = str.join("|", [str(row[0]) for row in data])
    else:
        every = xs / 10
        chxl = str.join("|", [ str(row[0]) for row 
                               in [ t[1] for t in enumerate(data)
                                    if t[0]%every==0 ] ])
    if colors: chco = str.join(",", colors)
    if axes: chdl = str.join("|", axes)
    if title: chtt = title.replace(" ", "+")

    return (("http://chart.apis.google.com/chart?" +
            "cht=%s&chs=800x375&chco=%s" +
            "&chd=t:%s&chds=%s&chdl=%s&chtt=%s" +
            "&chxt=x,y&chxr=1,0,%d,%d&chxl=0:|%s")
            % (cht, chco, 
               chd, chds, chdl, chtt, 
               M, chxr, chxl))

# format HTML result table
def prettyprint_time(t):
    s = t % 60
    r = t / 60
    m = r % 60
    r = r / 60
    h = r % 24
    d = r / 24
    
    v = "%d sec" % s
    if m>0: v = "%d min %s" % (m, v)
    if h>0: v = "%d hrs %s" % (h, v)
    if d>0: v = "%d days %s" % (d, v)

    return "%ds (%s)" % (t, v)
    
def prettyprint_num(t):
    return str(t)

if form.getvalue('y') in ['cputime', 'walltime']:
    prettyprint = prettyprint_time
else:
    prettyprint = prettyprint_num


def table_rows(data):
    return str.join("\n", 
                    [(" <tr>" 
                      + ("  <td>%s</td>" % row[0])
                      + str.join("\n",
                                 [("  <td>%s</td>" % prettyprint(val)) 
                                  for val in row[1:] ]) 
                      + " </tr>")
                     for row in data ])

# print out results (this is why people like templating languages...)
output = '''
<div style="text-align: center;">
 <img src="%s" />''' % chart_url(data, 
                                 [scope[0] for scope in scopes], 
                                 y_legend) + '''
</div>

<br />
<br />

<center>
<table>
 <tr>
  <th>Date</th>
''' + str.join("\n", [("  <th>%s</th>" % scope[0]) for scope in scopes]) + '''
 </tr>
''' + table_rows(data) + '''
</table>
</center>
'''

if form.has_key('ajax'):
    print output
else:
    # print full HTML doc
    values['content'] = output
    html = file('pbsplots.template.html', 'r').read()
    print html % values
