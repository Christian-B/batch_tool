import collections
import filecmp
import optparse  # using optparse as hydra still python 2.6
import os
import re
import shutil
import sys

parser = None


def report_error(error):
    """Prints the error, usage (if possible) and exits -1"""
    #print error
    if parser:
        # parser.print_help()
        print
        print error
    sys.exit(1)


def expanderuser(path):
    """Replaces the ~ with the users home directory"""
    if path.startswith("~"):
        return os.path.expanduser("~") + path[1: ]
    return path


def check_parent(parent):
    """Checks Parent directory exists and tries to make it of not"""
    if parent:
        if not os.path.isdir(parent):
            if os.path.isfile(parent):
                report_error("parent: " + parent + " is a file.")            
            grand_parent = os.path.dirname(os.path.normpath(parent))
            if (grand_parent):
                if os.path.isdir(grand_parent):
                    os.mkdir(parent, 0744)
                else:
                    report_error("grand parent (" + grand_parent + ") of " + parent + " does not exist.")
            else:
                os.mkdir(parent, 0744)
        if not os.path.isdir(parent):
            report_error("parent: " + parent + " does not exist.")
    else:
        raise Exception("Unexpected None parent")


def name_cleaner(root, name): 
    """Creates a useable path from a root and suggested name.

    The name if first cleaned to removed special characters.
    Whenever one or more is found a single underscore is added
    """
    name = name.replace("%", "_percent_")
    name = re.sub('[^0-9a-zA-Z]+', '_', name)
    if name[-1] == "_":
        name = name[: -1]
    if name[0] == "_":
        name = name[1: ]
    return os.path.join(root, name)


def copy_if_new(old_path, new_path, verbose=True):
    """Copies a file to a new location if required and safe.

    Checks if there is already a file at the new paths.
    Existing files are compared with the new file
    Rather than overwrite a different file the program exis with an error
    """
    if os.path.exists(new_path):
        if filecmp.cmp(new_path, old_path):
            if verbose:
                print "ignoring existing", new_path
        else:
            report_error("Unwilling to overwrite: " + new_path + " with " + old_path)
    else:
        shutil.copy2(old_path, new_path)
        if verbose:
            print new_path, "created"


def remove_symbols(s):
    if s.find("__") == -1:
        return s
    #Patterns used by Galaxy    
    s = s.replace("__cb__", ']')
    s = s.replace("__cc__", '}')
    s = s.replace("__dq__", '"')
    s = s.replace("__lt__", '<')
    s = s.replace("__gt__", '>')
    s = s.replace("__ob__", '[')
    s = s.replace("__oc__", '{')
    s = s.replace("__sq__", "'")
    # Patterns added by Christian
    s = s.replace("__in__",'%in%')
    s = s.replace("__not__",'!')
    end = -2
    while True:
        start = s.find("__", end+2) + 2
        if start == 1:
            return s
        end = s.find("__", start)
        if end == -1:
            return s
        part = s[start: end]
        try:
            ascii = int(part)
            s = s.replace("__" + part + "__",chr(ascii))
            end= -2
        except ValueError as e:
            pass
    return s


"""
File or directory processing methods

All will take three parameters
root: full path excluding the current directory or file
name: Name of the file or directory
verbose: flag to say if full output should be included
returns: True if and only if any subdirectories should be walked.
   Note: Return is only about subdirectores and not name!
"""


def approve_none(root, name, verbose=False):
    """Simple method to do nothing and ignore subdirectores"""
    return False


def approve_all(root, name, verbose=False):
    """Simple method to do nothing but walk any subdirectores"""
    return True


def print_size(root, name, verbose=False):
    """Debug method to print size of a file"""
    path = os.path.join(root, name)
    print path, "has size", os.path.getsize(path)


class RegexChecker:
    """Check a name against one or more regex"""

    def __init__(self, regexes=[".*"]):
        self.patterns = []
        for regex in regexes:
            self.patterns.append(re.compile(regex))

    def approve_name(self, root, name, verbose=False):
        """Returns true of name matches any of the regex"""
        for pattern in self.patterns:
            if pattern.search(name):
                return True
        return False


class FileSizeChecker:
    """Superclass of classes that could check the size of a file"""
    
    def __init__(self, maximum_size=None, minimum_size=None):
        if maximum_size is None:
            if minimum_size is None:
                self.size_wrong = self.never_wrong
            else:
                self.minimum_size = minimum_size
                self.size_wrong = self.too_small
        else:        
            self.maximum_size = maximum_size
            if minimum_size is None:
                self.size_wrong = self.too_big
            else:
                self.minimum_size = minimum_size
                self.size_wrong = self.outside_range
                
    def never_wrong(self, path):
        return False            
                
    def too_small(self, path):
        return os.path.getsize(path) < self.minimum_size
                 
    def too_big(self, path):
        #print path
        #print os.path.getsize(path) 
        #print os.path.getsize(path) > self.maximum_size
        return os.path.getsize(path) > self.maximum_size

    def outside_range(self, path):
        size = os.path.getsize(path)
        if (size < self.minimum_size):
            return True
        return os.path.getsize(path) > self.maximum_size

class DirectoryLister(FileSizeChecker):
    """Creates a list (to file) of the all suitable directories

    A directory is conidered suitable if
    Neither its name or any of its parents match the ignore_regexes
    It contains ALL of the required files
    """
    def __init__(self, list_file, ignore_regexes=[], required_files=[], check_path=None, list_path=None, maximum_size=None, minimum_size=None):
        """Sets up the class and stores all parameteres

        ignore_regexes: Pattern of all directories to ignore
            (including children directories of these)
        required_files: List of files that must all be present
            Missing a single one excludes the directory
        check_path and list_path: Allow you to check in one place and
            list in a different place
            if the path starts with check_path that is replaced with list_path
        """
        FileSizeChecker.__init__(self, maximum_size, minimum_size)
        self.ignore_patterns = []
        for regex in ignore_regexes:
            self.ignore_patterns.append(re.compile(regex))
        self.required_files = required_files
        self.check_path = check_path
        self.list_path = list_path
        if self.check_path:
            self.check_path = expanderuser(self.check_path)
            if not self.list_path:
                raise Exception("if check_path is specified a list_path is required")
            else:
                if self.list_path.startswith("~"):
                    raise Exception("Do not use ~ in list_path, as it does not work in all cases with all applications.")
        else:
            if self.list_path:
                raise Exception("if list_path is specified a check_path is required")
        self.list_file = expanderuser(list_file)
        try:
            afile = open(list_file, 'w')
            afile.close()
        except Exception as e:
            print e
            report_error("Unable to open file: " + list_file)

    def list_directory(self, root, name, verbose=True):
        """Processes the directory as per the settings passed on init"""
        for pattern in self.ignore_patterns:
            if pattern.search(name):
                # Ignore directory and its children
                return False
        path = os.path.join(root, name)
        for required_file in self.required_files:
            required_path = os.path.join(path, required_file)
            if not os.path.exists(required_path):
                # Ignore directory but check its children!
                if verbose:
                    print "ignoring", path, "as it is missing", required_file
                return True
            else:
                if (self.size_wrong(required_path)):
                    # Ignore directory but check its children!
                    if verbose:
                        print "ignoring", path, "as", required_file, "is the wrong size"
                    return True                
        if self.check_path:
            if path.startswith(self.check_path):
                path = self.list_path + path[len(self.check_path): ]
        with open(self.list_file, 'a') as f:
            f.write(path)
            f.write("\n")
        if verbose:
            print path, "added"
        return True


class Copier(FileSizeChecker):
    """Copies the files into seperate directories"""
    def __init__(self, endings_mappings, target_parent=os.getcwd(), maximum_size=None, minimum_size=None): 
        """Copies the files macthing endings_mappings into target_parent

        endings_mappings is a dictionary of regex terms to file endings
        Every time a file is found with matches the key and new file is
        created that with a name based on the directory name and the ending

        The program exits on an attempt to overwrite with a different file
        """
        FileSizeChecker.__init__(self, maximum_size, minimum_size)
        self.target_parent = expanderuser(target_parent)
        check_parent(self.target_parent)
        self.endings_mappings = {}
        try:
            if len(endings_mappings) == 0:
                raise Exception("endings_mappings may not be empty")
        except Exception as e:
            print e
            raise Exception("endings_mappings must be a dictionary")
        for(regex, file_name) in endings_mappings.items():
            pattern = re.compile(regex)
            self.endings_mappings[pattern] = file_name            

    def __act_on_files__(self, old_path, new_path, verbose=True):
        copy_if_new(old_path, new_path, verbose=verbose)
        return True

    def file_action(self, root, name, verbose=True):
        """Checks if name matches any regex pattern and if so copies the file

        As files are handled on at a time this methods copied the file
        even if the directory does not have all expected files
        """
        for(pattern, file_name) in self.endings_mappings.items():
            match = pattern.search(name)
            if match:
                prefix = name[: match.start()]
                if prefix[-1] == ".":
                    prefix = prefix[: -1]
                if len(prefix) == 0:
                    report_error("Ending regex: " + pattern.pattern + " was found at start of " + name )
                oldpath = os.path.join(root, name)
                if (self.size_wrong(oldpath)):
                    # Ignore directory but check its children!
                    if verbose:
                        print "ignoring", oldpath, "as it is the wrong size"
                    return False                
                newdir = os.path.join(self.target_parent, prefix)
                if not os.path.isdir(newdir):
                    os.mkdir(newdir)
                newpath = os.path.join(newdir, file_name)
                return self.__act_on_files__(oldpath, newpath, verbose)     
        return False

class Linker(Copier):
    """Links the files into a file in a seperate directory"""
    def __act_on_files__(self, old_path, new_path, verbose=True):
        if os.path.exists(new_path):
            try:
                with open(new_path, "r") as old_file:
                    old_link = old_file.read().replace('\n', '')
                if old_link != old_path:
                    if len(old_link) > 200:
                        report_error("Unwilling overwrite: " + new_path +
                                     " it does not apear to hold a link")
                    report_error("Unwilling overwrite: " + new_path +
                                " with " + old_path +
                                " it currently points to " + old_link)
            except Exception as e:
                print e
                raise Exception("Exception overwriting: " + new_path)
        with open(new_path, 'w') as f:
            f.write(old_path)
        if verbose:
            print old_path, "recorded at", new_path
        return True


class File_action:
    """Superclass of classes that write details to file"""

    def write_summary(self, path, root, summary):
        """Writes a line to path with root tab summary"""
        directory = os.path.basename(os.path.normpath(root))
        with open(path, 'a') as f:
            f.write(directory)
            f.write("\t")
            f.write(summary)
            if summary[-1] != "\n":
                f.write("\n")


class Extractor(File_action):
    """Extract information from the line that starts with extract_prefix

    Looks at any file whose name is in use_files
    Looks for a single line that starts with extract_prefix
    Strips of whitespace if requested to
    Writes this to summary_path
    """
    def __init__(self, summary_path, extract_prefix, use_files, strip=True):
        self.extract_prefix = extract_prefix
        if not self.extract_prefix:
            raise Exception("extract_prefix parameter(s) missing")
        if not isinstance(self.extract_prefix, basestring):
            raise Exception(self.extract_prefix, "is not a string")

        self.summary_path = summary_path
        try:
            afile = open(self.summary_path, 'w')
            afile.close()
        except Exception as e:
            print e
            raise Exception("Unable to open file: " + self.summary_path)

        self.use_files = use_files
        if not self.use_files:
            raise Exception("use_files parameter(s) missing or empty")
        if isinstance(self.use_files, basestring):
            self.use_file = [self.use_file]

        self.strip = strip

    def get_summary(self, root, name, verbose=True):
        """Summarizes the single line that starts with exact_prefix"""
        if name in self.use_files:
            path = os.path.join(root, name)
            summary = None
            with open(path, 'r') as the_file:
                for line in the_file:
                    if self.strip:
                        line = line.strip()
                    if line.startswith(self.extract_prefix):
                        if summary:
                            raise Exception("Two lines found in" + path + " which start with " + self.extract_prefix)
                        summary = line[len(self.extract_prefix): ]
                        if self.strip:
                            summary = summary.strip()
            if summary:
                self.write_summary(self.summary_path, root, summary)
                if verbose:
                    print path, "had", summary
            else:
                if verbose:
                    print self.prefix, "not found in ", path


class ByPrefixCombiner(File_action):
    """Extract information from each line that includes the divider

    Looks at any file whose name is in use_files
    Looks for lines with a the divider in them
    Writes what comes after the divider
    To a file whose names is based on what comes before the divider
    Strips of whitespace if requested to
    """

    def __init__(self, divider, use_files, output_dir=os.getcwd(), strip=True):
        """Sets the parameters for the combiner

        divider: String to act as the divider
        use_files: List of file names to check
        output_dir: Parent directory of all summary files
        """
        self.divider = divider
        if not self.divider:
            raise Exception("divider_prefix parameter(s) missing")
        if not isinstance(self.divider, basestring):
            raise Exception(self.divider, "is not a string")

        self.use_files = use_files
        if not self.use_files:
            raise Exception("use_files parameter(s) missing or empty")
        if isinstance(self.use_files, basestring):
            self.use_file = [self.use_file]

        self.output_dir = output_dir
        check_parent(self.output_dir)
        self.strip = strip
        self.summaries = collections.Counter()

    def get_summaries(self, root, name, verbose=True):
        """Extract data and appends to summary files"""
        if name in self.use_files:
            path = os.path.join(root, name)
            count = 0
            with open(path, 'r') as the_file:
                for line in the_file:
                    parts = line.split(self.divider)
                    if len(parts) == 2:
                        if self.strip:
                            for index in range(len(parts)):
                                parts[index] = parts[index].strip()
                        summary_file = name_cleaner(self.output_dir, parts[0]) + ".tsv"
                        self.write_summary(summary_file, root, parts[1])
                        self.summaries[summary_file] += 1
                        count += 1
                    elif len(parts) > 2:
                        raise Exception("file", path, "as a line with multiple", self.divider)
                if verbose:
                    print path, "contained", count, "lines with", self.divider

class Merger(FileSizeChecker):
    """Merges selected files into a single directory

    Looks for files whose name is one of the keys in file_mappings
    Copies a file to the target_parent with a name being a combination
    of the directory name and value in file_mappings
    """

    def __init__(self, file_mappings, target_parent=os.getcwd(), maximum_size=None, minimum_size=None):
        """Saves the parameters of a filE_mapping dictionary and target"""
        FileSizeChecker.__init__(self, maximum_size, minimum_size)
        self.target_parent = expanderuser(target_parent)
        check_parent(self.target_parent)
        self.file_mappings = file_mappings
        try:
            if len(file_mappings) == 0:
                raise Exception("file_mappings may not be empty")
        except Exception as e:
            print e
            raise Exception("file_mappings must be a dictionary")

    def copy_files(self, root, name, verbose=True):
        """Copies the file to the target_parent"""
        if name in self.file_mappings:
            old_path = os.path.join(root, name)
            if (self.size_wrong(old_path)):
                # Ignore directory but check its children!
                if verbose:
                    print "ignoring", old_path, "as it is the wrong size"
                return False                
            new_name = os.path.basename(root) + self.file_mappings[name]
            new_path = os.path.join(self.target_parent, new_name)
            copy_if_new(old_path, new_path, verbose=verbose)

class Filter(FileSizeChecker):
    """Copies the files into seperate directories"""
    def __init__(self, filter_mappings, keep_regexes, remove_regexes=list(), maximum_size=None, minimum_size=None, verbose=True): 
        """Copies the files matching endings_mappings based on keep_regexes and remove_regexs

        replace_mapping is a dictionary of regex terms to replacements
        Every time a file is found with matches the key a new file is
        created with the regex matched part of the name replaced by the value
        
        Only lines that contain at least one of the keep patterns are copied.
        From these any part that matches any remove regex is replace by an empty string

        The program exits on an attempt to overwrite with a different file
        """
        FileSizeChecker.__init__(self, maximum_size, minimum_size)
        self.filter_mappings = {}
        try:
            if len(filter_mappings) == 0:
                raise Exception("filter_mappings may not be empty")
        except Exception as e:
            print e
            raise Exception("filter_mappings must be a dictionary")
        for(regex, replace) in filter_mappings.items():
            pattern = re.compile(regex)
            self.filter_mappings[pattern] = replace

        self.keep_patterns = list()
        try:
            if len(keep_regexes) == 0:
                raise Exception("keep_regexes may not be empty")
        except Exception as e:
            print e
            raise Exception("keep_regexes must be a list")
        for regex in keep_regexes:
            if verbose:
                print "Will keep any line that has: ", regex
            pattern = re.compile(remove_symbols(regex))
            self.keep_patterns.append(pattern)
        self.remove_patterns = list()
        for regex in remove_regexes:
            if verbose:
                print "Will remove any text that matches: ", regex
            pattern = re.compile(remove_symbols(regex))
            self.remove_patterns.append(pattern)

    def __keep_line__(self, line):
        for pattern in self.keep_patterns:
            match = pattern.search(line)
            if match:
                return True
        return False

    def __copy_and_filter__(self, old_path, new_path, verbose=True):
        #if os.path.exists(new_path):
        #    report_error("Unwilling to overwrite: " + new_path + " with " + old_path)
        #else:
            with open(old_path, 'r') as old_f:
                with open(new_path, 'w') as new_f:
                    for line in old_f:
                        if self.__keep_line__(line):
                            line = line
                            for remove_pattern in self.remove_patterns:
                                #print remove_pattern.pattern
                                line = remove_pattern.sub("", line)
                                #print line
                            line = line.strip()
                            new_f.write(line)
                            new_f.write("\n")

    def file_action(self, root, name, verbose=True):
        """Checks if name matches any regex pattern and if so copies the file

        """
        for(pattern, replace) in self.filter_mappings.items():
            match = pattern.search(name)
            if match:
                oldpath = os.path.join(root, name)
                if (self.size_wrong(oldpath)):
                    # Ignore directory but check its children!
                    if verbose:
                        print "ignoring", oldpath, "as it is the wrong size"
                    return False                
                newname = re.sub(pattern.pattern, replace, name)
                newpath = os.path.join(root, newname)
                return self.__copy_and_filter__(oldpath, newpath, verbose)     
        return False

def do_walk(source=os.getcwd(), directory_action=approve_all, file_action=print_size, onerror=None, followlinks=False, verbose=True):
    """
    Walker method
    Inputs are:
    source Parent directory to be walked through
    directory_action method to process and check subdirectoies
        method may do something useful but must return a boolean
        approve_all(default) cause all children(recurisive) to be walked
        approve_none ignores all child directories
    file_action method processes each file
        can but needs not do anything
        any return is ignored
        print_size(default) just prints the path and size
    onerror is a function on underlying os.listdir fails
    followlinks would allow following symbolic links
        WARNING Be aware that setting followlinks to True can lead to infinite
           recursion if a link points to a parent directory of itself.
           walk() does not keep track of the directories it visited already.
    verbose: Flag passed to action methods to provide more output
    """
    source = expanderuser(source)
    # Must be topdown=True otherwise walk will process subdirectories before checking them
    for root, dirs, files in os.walk(source, topdown=True, onerror=onerror, followlinks=followlinks):
        dirs_clone = dirs[: ]
        for sub in dirs_clone:
            if not directory_action(root, sub, verbose=verbose):
                if verbose:
                    print "skipping directory", os.path.join(root, sub)
                dirs.remove(sub)
        # do something cool with each file
        for name in files:
            file_action(root, name, verbose=verbose)

"""
Methods for creating batch job file
"""


def count_lines(file_name):
    """Counts the number of lines in a file"""
    lines = 0
    with open(file_name) as the_file:
        for line in the_file:
            lines += 1
    return lines


def write_loop_block(new_file, directory_list):
    """Insters the instuctions to do a job array based on a directpry file"""
    count = count_lines(directory_list)
    new_file.write("#$ -t 1-")
    new_file.write(str(count))
    new_file.write("\n")
    new_file.write("DIRECTORY=`sed -n \"${SGE_TASK_ID}p\" ")
    new_file.write(directory_list)
    new_file.write("`\n")
    new_file.write("\n")


def update_script(script, new_script, directory_list):
    """Converts a none job script into a job array script

    Assumes that the first instruction is a line that starts with "DIRECTORY="
    Replaces that line with the looping instructions
       inluding to look for the directories in the directory_list file.
    """
    directory_line_found = False
    with open(script) as old_file:
        with open(new_script, 'w') as new_file:
            for line in old_file:
                if line.startswith("DIRECTORY="):
                    if directory_line_found:
                        raise Exception("qsub_file: " + script + " has two lines that start with DIRECTORY=")
                    else:
                        write_loop_block(new_file, directory_list)
                        directory_line_found = True
                else:
                    new_file.write(line)
    if not directory_line_found:
        raise Exception("qsub_file: " + script + " has no line that start with DIRECTORY=")


def short(term):
    """Converts a parameter name into a short flag"""
    return "-" + term.lower()[0]


def longer(term):
    """Converts a parameter name into a long flag"""
    return "--" + term.lower()

"""Commands for the program"""
__FIND__ = "find"
__LIST__ = "list"
__BATCH__ = "batch"
__EXTRACT__ = "extract"
__DELIMIT__ = "delimit"
__MERGE__ = "merge"
__FILTER__ = "filter"
__COMMANDS__ = [__FIND__, __LIST__, __BATCH__, __EXTRACT__, __DELIMIT__, __MERGE__, __FILTER__]

"""Parameter names"""
#__AFTER_DATE__ = "AFTER_DATE"
__BATCH_SCRIPT__ = "BATCH_SCRIPT"
__COPY__ = "COPY"
__DELIMITER__ = "DELIMITER"
__EXTRACT_PREFIX__ = "EXTRACT_PREFIX"
__FILE_LIST__ = "FILE_LIST"
__LISTp__ = "LIST"
__KEEP_REGEX__ = "KEEP_REGEX"
__MINIMUM_SIZE__ = "MINIMUM_SIZE"
__MAXIMUM_SIZE__ = "MAXIMUM_SIZE"  #short = x
__OUTPUT_DIR__ = "OUTPUT_DIR"
__PARENT__ = "PARENT"
__QSUB_SCRIPT__ = "QSUB_SCRIPT"
__REMOVE_REGEX__ = "REMOVE_REGEX"
__SOURCE__ = "SOURCE"
#__UPTO_DATE__ = "UPTO_DATE"
__VERBOSE__ = "VERBOSE"
#X" used for maximum

#Directory lister ignore
#Directory lister check vs list path


if __name__ == '__main__':
    usage = "usage: %prog command(s) [options] \n" + \
            "Where command(s) is one or more of " + str(__COMMANDS__)
    parser = optparse.OptionParser(usage=usage)
    parser.add_option(short(__VERBOSE__ ), longer(__VERBOSE__ ), action="store_true", dest=__VERBOSE__, default=False,
                  help="If set will generate output of what the tool is doing.")

    find_group = optparse.OptionGroup(parser, __FIND__,
                    "Searchs though the " + __SOURCE__ + " directory(and subdirectories) "
                    "looking for file that match the regex pattern in " + __FILE_LIST__ + "(s)."
                    "For file that matches the regex pattern, the part before the pattern is used as the name of "
                    "a subdirectory of " + __PARENT__ + " to be created/used. "
                    "Anything after the pattern is ignored. "
                    "A new file is created with either a link or copy. "
                    'Example: find --file_list="R1_001.fastq.gz:left.link" --file_list="R2_001.fastq.gz:right.link" '
                    )
    find_group.add_option(short(__SOURCE__), longer(__SOURCE__) , dest=__SOURCE__, action="store", type="string",
                  default=os.getcwd(),
                  help=__SOURCE__ + "directory that holds the raw data files. "
                  "Default is the current directory")
    find_group.add_option(short(__PARENT__), longer(__PARENT__), dest=__PARENT__, action="store", type="string",
                  default=os.getcwd(),
                  help=__PARENT__ + " directory of the sub directories to hold the data for each run "
                  "Default is the current directory")
    parent_option = find_group.get_option(longer(__PARENT__))
    find_group.add_option(short(__FILE_LIST__), longer(__FILE_LIST__) , dest=__FILE_LIST__ , action="append", type="string",
                  help="List of files to operate over. "
                       "If " + __FIND__ + " specified, format must be regex:name "
                       "If " + __MERGE__ + " is specified, format must be ending:name  "
                       "If " + __FILTER__ + " is specified, format must be regex:replacement  "
                       "Otherwise format can be just the name. "
                       "Multiple values allowed.")
    file_list_option = find_group.get_option(longer(__FILE_LIST__ ))
    find_group.add_option(short(__MINIMUM_SIZE__), longer(__MINIMUM_SIZE__) , dest=__MINIMUM_SIZE__ , action="store", type="long",
                  help="Minimum size in bytes that a file must have to be used.")
    minimum_size_option = find_group.get_option(longer(__MINIMUM_SIZE__))
    find_group.add_option("-X", longer(__MAXIMUM_SIZE__) , dest=__MAXIMUM_SIZE__ , action="store", type="long",
                  help="Maximum size in bytes that a file must have to be used.")
    maximum_size_option = find_group.get_option(longer(__MAXIMUM_SIZE__))
    
    find_group.add_option(short(__COPY__), longer(__COPY__), action="store_true", dest=__COPY__, default=False,
                  help="(Optional) If specified will copy the original file to the new location. "
                       "Otherwise just the path to the original file is saved.")
    parser.add_option_group(find_group)

    list_group = optparse.OptionGroup(parser, __LIST__,
                     "Lists all the paths to the directories "
                     "(including subdirectories) in " + __PARENT__ + " directory"
                     "But only includes the directories that contain a  files in " + __FILE_LIST__ + "(s)"
                     "This list is writen to the path specified as " + __LISTp__ + "  "
                     'Example: list --file_list="left.link" --file_list="right.link"'
                     )
    list_group.option_list.append(parent_option)
    list_group.option_list.append(file_list_option)
    list_group.option_list.append(minimum_size_option)
    list_group.option_list.append(maximum_size_option)
    list_group.add_option(short(__LISTp__), longer(__LISTp__), dest=__LISTp__, action="store", type="string",
                  default="directories.txt",
                  help="File to hold the list of directories. "
                  "Default is directories.txt in the current directory.")
    list_option = list_group.get_option(longer(__LISTp__))
    parser.add_option_group(list_group)

    batch_group = optparse.OptionGroup(parser, __BATCH__,
                     "Converts the " + __QSUB_SCRIPT__ + " to a batch/job array "
                     "The batch will run over each directory in the " + __LISTp__)
    batch_group.option_list.append(list_option)
    batch_group.add_option(short(__QSUB_SCRIPT__), longer(__QSUB_SCRIPT__), dest=__QSUB_SCRIPT__, action="store", type="string",
                  help="qsub script to be switched to batch. "
                       "This script should have a line which starts with DIRECTORY= "
                       "This line will be replaced with a loop for each directory in the " + __LISTp__)
    batch_group.add_option(short(__BATCH_SCRIPT__), longer(__BATCH_SCRIPT__), dest=__BATCH_SCRIPT__, action="store", type="string",
                  help="Location to write batch qsub script to. "
                       "Default is " + __QSUB_SCRIPT__ + " + \"_batch\" ")
    parser.add_option_group(batch_group)

    extract_group = optparse.OptionGroup(parser, __EXTRACT__,
                     "Extract information from the files in " + __PARENT__ + " directory "
                     "(and sub directories) "
                     "whose name are in the " + __FILE_LIST__ + "(s)"
                     "Looking for a line that begins with the " + __EXTRACT_PREFIX__ + " "
                     "These will be written to a file called " + __EXTRACT_PREFIX__ + ".tsv "
                     "Placed in the " + __OUTPUT_DIR__ )
    extract_group.option_list.append(parent_option)
    extract_group.option_list.append(file_list_option)
    extract_group.add_option(short(__EXTRACT_PREFIX__), longer(__EXTRACT_PREFIX__), dest=__EXTRACT_PREFIX__,
                  action="append", type="string",
                  help="Prefix of the line to extract information from.")
    extract_group.add_option(short(__OUTPUT_DIR__), longer(__OUTPUT_DIR__), dest=__OUTPUT_DIR__, action="store", type="string",
                  help="Directories to hold the file(s). "
                  "Default is " + __PARENT__)
    output_option = extract_group.get_option(longer(__OUTPUT_DIR__))
    parser.add_option_group(extract_group)

    delimit_group = optparse.OptionGroup(parser, __DELIMIT__,
                     "Extract information from the files in the " + __PARENT__ + " directory "
                     "(and sub directories) "
                     "whose name are in the " + __FILE_LIST__ + "(s) "
                     "Looking for lines with the delimiter in them."
                     "Saving what comes after the " + __DELIMITER__ + " +  in a file whose "
                     "name is based on what comes before the delimieter"
                     "Placed in the " + __OUTPUT_DIR__ )
    delimit_group.option_list.append(parent_option)
    delimit_group.option_list.append(file_list_option)
    delimit_group.add_option(short(__DELIMITER__), longer(__DELIMITER__), dest=__DELIMITER__, action="store", type="string",
                  help="Delimiter to create extract information files with."
                       "Will look in all files in the directories specified by parent that are in the file_list."
                       "For each line with this delimiter it will not the rest in a summary file."
                       "This data will be written to a tsv file in the parent directory.")
    delimit_group.option_list.append(output_option)
    parser.add_option_group(delimit_group)

    merge_group = optparse.OptionGroup(parser, __MERGE__,
                     "Merges files found in the " + __PARENT__ + " directory (and sub directories) "
                     "whose name are in the name part of " + __FILE_LIST__ + "(s) "
                     "Coping these with a file whose name is based on the directory "
                     "and the ending part of " + __FILE_LIST__ + "(s) "
                     "Placed in the " + __OUTPUT_DIR__ )
    merge_group.option_list.append(parent_option)
    merge_group.option_list.append(file_list_option)
    merge_group.option_list.append(output_option)
    parser.add_option_group(merge_group)

    filter_group = optparse.OptionGroup(parser, __FILTER__,
                     "Filters files found in the " + __PARENT__ + " directory (and sub directories) "
                     "whose name match the regex part of " + __FILE_LIST__ + "(s) "
                     "Coping these with a file whose name is the regex part replaced with the replacement part of " + __FILE_LIST__ + ". "
                     "Placed in the " + __OUTPUT_DIR__ )
    filter_group.option_list.append(parent_option)
    filter_group.option_list.append(file_list_option)
    filter_group.add_option(short(__KEEP_REGEX__), longer(__KEEP_REGEX__), dest=__KEEP_REGEX__, action="append", type="string",
                  help="Regex pattern to idenfity a line that should be kept. "
                       "Multiple values are allowed in which case any line which has any of the values is kept.")
    filter_group.add_option(short(__REMOVE_REGEX__), longer(__REMOVE_REGEX__), dest=__REMOVE_REGEX__, action="append", type="string",
                  help="Regex pattern to idenfity parts of the lines to remove. "
                       "Multiple values are allowed in which they are applied in the order provided." 
                       "The same pattern can be used for both a " + __KEEP_REGEX__ + " and a " + __REMOVE_REGEX__ + ". ")
    filter_group.option_list.append(output_option)
    parser.add_option_group(filter_group)
    
    (options, args) = parser.parse_args()

    if len(args) == 0:
        report_error("No command specified! Legal commands are: " + str(__COMMANDS__))

    for arg in args:
        if arg not in __COMMANDS__:
            report_error("Unexpected command " + arg + " Legal commands are: " + str(__COMMANDS__))

    endings_mappings = None
    required_files = None
    if __FIND__ in args:
        if __MERGE__ in args:
            report_error(__FIND__ + " and " + __MERGE__ +
                         " can not be combined due to different " + __FILE_LIST__ + " formats")
        if __FILTER__ in args:
            report_error(__FIND__ + " and " + __FILTER__ +
                         " can not be combined due to different " + __FILE_LIST__ + " formats")
        if not options.__dict__[__FILE_LIST__]:
            report_error(__FIND__ + " selected but no " + __FILE_LIST__ + " parameter provided")
        endings_mappings = {}
        for file_option in options.__dict__[__FILE_LIST__]:
            parts = file_option.split(":")
            if len(parts) != 2:
                report_error(__FILE_LIST__ + " " + file_option + " not in the expected regex:name format")
            endings_mappings[parts[0]] = parts[1]
        required_files = endings_mappings.values()
    elif __MERGE__ in args:
        if __FILTER__ in args:
            report_error(__MERGE__ + " and " + __FILTER__ +
                         " can not be combined due to different " + __FILE_LIST__ + " formats")
        if not options.__dict__[__FILE_LIST__]:
            report_error(__MERGE__ + " selected but no " + __FILE_LIST__ + " parameter provided")
        file_mappings = {}
        for file_option in options.__dict__[__FILE_LIST__]:
            parts = file_option.split(":")
            if len(parts) != 2:
                report_error(__FILE_LIST__ + " " + file_option + " not in the expected ending:name format")
            file_mappings[parts[1]] = parts[0]
    elif __FILTER__ in args:
        if not options.__dict__[__FILE_LIST__]:
            report_error(__MERGE__ + " selected but no " + __FILE_LIST__ + " parameter provided")
        filter_mappings = {}
        for file_option in options.__dict__[__FILE_LIST__]:
            parts = file_option.split(":")
            if len(parts) != 2:
                report_error(__FILE_LIST__ + " " + file_option + " not in the expected ending:name format")
            filter_mappings[parts[0]] = parts[1]
    elif options.__dict__[__FILE_LIST__]:
        required_files = []
        for file_option in options.__dict__[__FILE_LIST__]:
            parts = file_option.split(":")
            if len(parts) == 1:
                required_files.append(parts[0])
            elif len(parts) == 2:
                required_files.append(parts[1])
            else:
                report_error("FILE_LIST " + file_option + " has more than one : in it.")

    if not options.__dict__[__OUTPUT_DIR__]:
        options.__dict__[__OUTPUT_DIR__] = options.__dict__[__PARENT__]

    options.__dict__[__LISTp__] = expanderuser(options.__dict__[__LISTp__])

    if __FIND__ in args:
        # parent, source and copy have default values
        # File list already checked
        if options.__dict__[__COPY__]:
            copier = Copier(endings_mappings, options.__dict__[__PARENT__],
                            minimum_size=options.__dict__[__MINIMUM_SIZE__], maximum_size=options.__dict__[__MAXIMUM_SIZE__])
            print "Coping files from", options.__dict__[__SOURCE__], "to", options.__dict__[__PARENT__]
        else:
            copier = Linker(endings_mappings, options.__dict__[__PARENT__],
                            minimum_size=options.__dict__[__MINIMUM_SIZE__], maximum_size=options.__dict__[__MAXIMUM_SIZE__])
            print "linking files from", options.__dict__[__SOURCE__], "in", options.__dict__[__PARENT__]
        print "Using the file mappings: "
        print endings_mappings
        do_walk(source=options.__dict__[__SOURCE__], directory_action=approve_all, file_action=copier.file_action,
                verbose=options.__dict__[__VERBOSE__])
        if options.__dict__[__VERBOSE__]:
            print

    if __LIST__ in args:
        # parent has a default value
        if not required_files:
            report_error(__LIST__ + " selected but no " + __FILE_LIST__ + " parameter provided")
        print "Writing list of directories in", options.__dict__[__PARENT__], "to", options.__dict__[__LISTp__]
        print "Only directories that have all these files are included: "
        print required_files
        lister = DirectoryLister(list_file=options.__dict__[__LISTp__], required_files=required_files, 
                                 minimum_size=options.__dict__[__MINIMUM_SIZE__], maximum_size=options.__dict__[__MAXIMUM_SIZE__]) 
        do_walk(source=options.__dict__[__PARENT__], directory_action=lister.list_directory, file_action=approve_none,
                verbose=options.__dict__[__VERBOSE__])
        if options.__dict__[__VERBOSE__]:
            print

    if __BATCH__ in args:
        if not options.__dict__[__QSUB_SCRIPT__]:
            report_error(__BATCH__ + " selected but no " + __QSUB_SCRIPT__ + " parameter provided")
        if options.__dict__[__BATCH_SCRIPT__]:
            batch = options.__dict__[__BATCH_SCRIPT__]
        else:
            batch = options.__dict__[__QSUB_SCRIPT__] + "_batch"
        print "Writing new",__BATCH_SCRIPT__,"to", batch
        print "Based on", __QSUB_SCRIPT__, options.__dict__[__QSUB_SCRIPT__]
        print "Using directory LIST", options.__dict__[__LISTp__]
        update_script(options.__dict__[__QSUB_SCRIPT__], batch, options.__dict__[__LISTp__])
        if options.__dict__[__VERBOSE__]:
            print

    if __EXTRACT__ in args:
        if not options.__dict__[__EXTRACT_PREFIX__]:
            report_error(__EXTRACT__ + " selected but no " + __EXTRACT_PREFIX__ + " parameter provided")
        if not required_files:
            report_error(__EXTRACT__ + " selected  but no " + __FILE_LIST__ + " parameter provided")
        for extract_prefix in options.__dict__[__EXTRACT_PREFIX__]:
            summary_path = name_cleaner(options.__dict__[__OUTPUT_DIR__], extract_prefix) + ".tsv"
            print "Writing extract to ", summary_path
            extractor = Extractor(summary_path, extract_prefix, required_files, strip=True)
            do_walk(source=options.__dict__[__PARENT__], directory_action=approve_all, file_action=extractor.get_summary,
                    verbose=options.__dict__[__VERBOSE__])
        if options.__dict__[__VERBOSE__]:
            print

    if __DELIMIT__ in args:
        if not options.__dict__[__DELIMITER__]:
            report_error(__DELIMIT__ + " selected but no " + __DELIMITER__ + " parameter provided")
        if not required_files:
            report_error(__DELIMIT__ + " selected  but no FILE_LIST parameter provided")
        print "Writing extract to ", options.__dict__[__OUTPUT_DIR__]
        combiner = ByPrefixCombiner(options.__dict__[__DELIMITER__], required_files,
                                    options.__dict__[__OUTPUT_DIR__], strip=True)
        do_walk(source=options.__dict__[__PARENT__], directory_action=approve_all,
                file_action=combiner.get_summaries, verbose=options.__dict__[__VERBOSE__])
        if options.__dict__[__VERBOSE__]:
            for key in sorted(combiner.summaries):
                print key, combiner.summaries[key]
        if options.__dict__[__VERBOSE__]:
            print

    if __MERGE__ in args:
        print "Coping files to ", options.__dict__[__OUTPUT_DIR__]
        merger = Merger(file_mappings, options.__dict__[__OUTPUT_DIR__], 
                        minimum_size=options.__dict__[__MINIMUM_SIZE__], maximum_size=options.__dict__[__MAXIMUM_SIZE__])
        do_walk(source=options.__dict__[__PARENT__], directory_action=approve_all,
                file_action=merger.copy_files, verbose=options.__dict__[__VERBOSE__])
        if options.__dict__[__VERBOSE__]:
            print

    if __FILTER__ in args:
        if not options.__dict__[__PARENT__]:
            report_error(__FILTER__ + " selected but no " + __PARENT__ + " parameter provided")
        print "Coping and filtering files to ", options.__dict__[__PARENT__]
        if not filter_mappings:
            report_error(__FILTER__ + " selected  but no "+ __FILE_LIST__ + " parameter provided")
        if not options.__dict__[__KEEP_REGEX__]:
            report_error(__FILTER__ + " selected but no " + __KEEP_REGEX__ + " parameter provided")
        if not options.__dict__[__REMOVE_REGEX__]:
             options.__dict__[__REMOVE_REGEX__] = list()
        filter = Filter(filter_mappings, options.__dict__[__KEEP_REGEX__], options.__dict__[__REMOVE_REGEX__],  
                        minimum_size=options.__dict__[__MINIMUM_SIZE__], maximum_size=options.__dict__[__MAXIMUM_SIZE__], verbose=options.__dict__[__VERBOSE__])
        do_walk(source=options.__dict__[__PARENT__], directory_action=approve_all,
                file_action=filter.file_action, verbose=options.__dict__[__VERBOSE__])
        if options.__dict__[__VERBOSE__]:
            print

