This tool is used to support running job array scripts

### Preprocessing steps
1. Find the required files and link/copy them into seperate directories
- default: only create a tiny file with the link to the file
- copy: will create a copy to the file
2. List directories containing the required files into a file
3. Batch: Convert a job script to a job array script based on a list of directories
 
### Run job array

### Post processing steps
4. Extract some information from one line in one file in each directory 
5. Delimit: Extract information for files, in each directory, based on a single delimiter 
6. Merge files from various directories back into a single directory

### Usage
See [Usage](https://github.com/Christian-B/batch_tool/blob/master/usage.txt) for parameters for each step
Or run python batch_tools.py --help

# Details

## Notes

### Paths
- All examples use relative paths for cross compute usage
- If relative paths are used the link files creted by find and the list file will be relative
- Remember that the paths must work where the grid job is run!
- Avoid using ~. As ~ does not work for all appliactions it will be replace with the home directory.

### Symlinks
- Currently the code does not follow any symlinks.
- Following syslinks can easily be added but could cause endless recursion.

### Minimun and Maximun
- These values are in bytes and inclusive ends so minimum_size=0 will include an empty file.

## find 
Will go through the source directory(and all child directories) looking for files whose name matches the regex.

Everything in the file before the regex is used as the name for a new directory.

A new file is written containing the link (find) or copy of the file using the new name.

The tool should not overwrite an existing file instead throwing an error it the new file would be different to an existing one. 

### file_list
The file_list parameter must be in two parts. (Seperated by a :)
1. Regex part:  The regex to check files against
2. The new name to assign the file

If the regex contains wildcard characters and more than one file has the same prefix followed by the pattern an error is likely to occur, when the second link or file is created where one already exists.

Multiple file_list parameters are allowed. A file is linked/copied if it matches any of the regex patterns.

### Examples
```
python batch_tools.py find --source=sample_data/single_folder --parent=output --file_list=_data:data.link --verbose 

python batch_tools.py find --source=sample_data/single_folder --parent=output --file_list=_data:the_data.txt --minimum_size=100 --maximum_size=10000 --copy --verbose 
```

## list
Will go through the parent directory(and all child directories) looking for directories that have ALL the reguired files.

### file_list
Multiple file_list parameters are allowed. To be listed a directory must contain all the files.

Only the file name is required.
-To be compatibale with find anything upto and including a : is ignored

### Maximun and Minimun size.
These opertor on the file found in the directory. They will NOT follow links created by find to check the original file.

### Examples
```
python batch_tools.py list --parent=sample_data/multiple_folders --file_list=data.link --list=output/directories.txt --verbose 

python batch_tools.py list --parent=sample_data/multiple_folders --file_list=the_data.txt --list=output/empty.txt --maximum_size=0 --verbose 
```

## batch
Converts a specific single run grid script into a job array grid script

Replacing the line:
DIRECTORY=$1

With a loop that reads each path in the list into DIRECTORY to run as a subjob.
 
### The script
This script should have the line:

DIRECTORY=$1

Probaby followed with the line
cd th $DIRECTORY

The script then reads local files in this directory and writes output into this directory

### Example
```
python batch_tools.py batch --list=sample_data/directories.txt --qsub_script=sample_data/batch_stud.sh --batch_script=output/job_array_script.sh --verbose 
```

## find, list, batch in one call
It is possible to all the preprocessing steps in a single call

###
Example
```
python batch_tools.py find list --source=sample_data/single_folder --parent=output --file_list=_data:data.link --list=sample_data/directories.txt --qsub_script=sample_data/batch_stud.sh --batch_script=output/job_array_script.sh --verbose 
```

## Extract
Walks through the parent dicertory and all children, looking for files in the file_list and the for a single line that starts with an extract_prefix.

For each extract_prefix a summary file is created in output_dir with the name of the folder and the remainder of that line for each directory.

### file_list
While muiltple values are allowed the output files will only report the directory the data was found in and not the specific file.

### Example
```
python batch_tools.py extract --parent=sample_data/multiple_folders --file_list=report.txt --extract_prefix="Lines |" --output_dir=output  --verbose
```

## Delimit
Walks through the parent dicertory and all children, looking for files in the file_list and any line that contains the delimiter

For each prefix (found before the delimiter) a summary file is created in output_dir with the name of the folder and the remainder of that line for each directory.

### Example
```
python batch_tools.py delimit --parent=sample_data/multiple_folders --file_list=report.txt --delimiter="|" --output_dir=output  --verbose
```

## Merge
Walks through the parent dicertory and all children, looking for files in the file_list.

For each file found a copy is created in output_dir with the name being the directory name + ending.

### file_list
The file_list parameter must be in two parts. (Seperated by a :)
1. The ending part of the new file.
2. The name to the file to copy

### Examples
```
python batch_tools.py merge --parent=sample_data/multiple_folders --file_list=_result.txt:report.txt --output_dir=output --verbose 

python batch_tools.py merge --parent=sample_data/multiple_folders --file_list=_data.txt:the_data.txt --output_dir=output --minimum_size=100 --maximum_size=10000 --verbose 
```

## list
The preprocessing list could also be used for postprocessing, for example to find all the directories where the job failed and created just an empty file.

This list could then be used for manual checking or even rerunning just the failed jobs. 


## Filter
Walks through the directory making copies of some files but filtering out unwanted parts

For each file found a copy is created in the same directory with the regex part of the name replaced by the replacement

However only lines that match one of the keep_regex patterns are copied.
And even from these any parts that matches any --remove_regex are removed.

### file_list
The file_list parameter must be in two parts. (Seperated by a :)
1. The regex to identify the file(s) to copy
2. The replacement to swap for the part matched by the regex

### Examples
```
rm sample_data/logs/*filtered_log.txt

python batch_tools.py filter --source=sample_data/logs  --file_list=R1_logfile.txt$:filtered_log.txt --keep_regex ERCC-000 --remove_regex \\[.*\\] --verbose 
```



