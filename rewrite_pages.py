import sys, os, subprocess
import json
from typing import Dict, List, Set
from random import randint, seed
from shutil import copytree, rmtree
from os.path import join

_INST_DIR: str = 'horcrux-instrumentation-rewriter/instrumentation/'
_CHROME_JS: str = os.path.abspath('chrome.js')
ITERATION_MAX: int = 1

def run_command(command: str) -> str:
    completed = subprocess.run(command, shell=True, capture_output=True)
    if completed.returncode != 0:
        raise RuntimeError(f"Failed to run {command}" \
                           f"-> {completed.stderr.decode('utf-8')}")
    else:
        return completed.stdout.decode('utf-8')[:-1] # drop the trailing \n


def num_of_files_in(dir: str) -> int:
    return len([name for name in os.listdir(dir)])


def read_url_list(path: str) -> List[str]:
    url_list: List[str] = []
    with open(path, 'r') as f_list:
        url_list = f_list.readlines()
    url_list = list(map(lambda l: l.strip(), url_list))
    url_list = list(filter(lambda url: not url.startswith('#'), url_list))
    return url_list


def light_instrument(input_dir: str, output_dir: str):
    page_url: str = os.path.basename(input_dir)
    log_dir: str = join(output_dir, 'logs-light')
    step_one_cmd: str = "python2 readHTTPResponse.py" \
                    f" {input_dir} {output_dir} cg {log_dir}"
    count = 0
    while count < 3:
        run_command(step_one_cmd)
        generated_dir: str = join(output_dir, page_url)
        if num_of_files_in(input_dir) == num_of_files_in(generated_dir):
            os.rename(generated_dir, join(output_dir, 'light'))
            return
        else:
            count += 1
    raise RuntimeError(f"Step one failed: mismatched number of protobufs")


def timing_instrument(input_dir: str, output_dir: str):
    page_url: str = os.path.basename(input_dir)
    log_dir: str = join(output_dir, 'logs-timing')
    step_two_cmd: str = "python2 readHTTPResponse.py" \
                    f" --cgInfo {join(output_dir, 'roots-nc.json')}" \
                    f" {input_dir} {output_dir} cg {log_dir}"
    count = 0
    while count < 3:
        run_command(step_two_cmd)
        generated_dir: str = join(output_dir, page_url)
        if num_of_files_in(input_dir) == num_of_files_in(generated_dir):
            os.rename(generated_dir, join(output_dir, 'timing'))
            return
        else:
            count += 1
    raise RuntimeError(f"Step two failed: mismatched number of protobufs")


def heavy_instrument(input_dir: str, output_dir: str):
    page_url: str = os.path.basename(input_dir)
    log_dir: str = join(output_dir, 'logs-heavy')
    step_three_cmd: str = "python2 readHTTPResponse.py" \
                    f" --cgInfo {join(output_dir, 'roots-nc.json')}" \
                    f" {input_dir} {output_dir} record {log_dir}"
    count = 0
    while count < 3:
        run_command(step_three_cmd)
        generated_dir: str = join(output_dir, page_url)
        if num_of_files_in(input_dir) == num_of_files_in(generated_dir):
            os.rename(generated_dir, join(output_dir, 'heavy'))
            return
        else:
            count += 1
    raise RuntimeError(f"Step three failed: mismatched number of protobufs")


def rewrite_instrument(input_dir: str, output_dir: str):
    if (os.path.isdir(join(output_dir, 'rewrite'))):
        return
    page_url: str = os.path.basename(input_dir)
    log_dir: str = join(output_dir, 'logs-rewrite')
    step_four_cmd: str = "python2 readHTTPResponse.py" \
        f" --cgInfo {join(output_dir, 'roots-nc.json')}" \
        f" --callGraph {join(output_dir, 'call-graph-nc.json')}" \
        f" --signature {join(output_dir, 'signature-final.json')}" \
        f" {input_dir} {output_dir} rewrite {log_dir}"
    run_command(step_four_cmd)
    generated_dir: str = join(output_dir, page_url)
    if num_of_files_in(input_dir) == num_of_files_in(generated_dir):
        os.rename(generated_dir, join(output_dir, 'rewrite'))
    else:
        raise RuntimeError(f"Step three failed: mismatched number of protobufs")


def load_page(page_name: str, output_dir: str, mode:str,
              output_file: str, extra_output_file: str = None):
    """ Loads the mode(light/timing/heavy) mahimahi folder under output_dir
    with --mode, and other extra flags corresponding to mode.
    Stores the roots/timing/signatures in the given output_file.
    The extra output file is required, if mode is light or timing which is where
    the call graph/PLT timings are saved to.
    """
    mm_dir: str = join(output_dir, mode)
    load_cmd: str = f"mm-webreplay {mm_dir}" \
                    f" node {_CHROME_JS} -u https://{page_name}" \
                    f" -p {randint(9000, 9500)}"
    if mode in ['light', 'timing', 'heavy', 'none']:
        load_cmd += f" -m {mode}"
    else:
        raise RuntimeError(f"Wrong mode for loading the page: '{mode}'")
    load_cmd += f" -o {output_file}"
    # adding extra options for generating other files besides the output_file
    if mode == 'light':
        load_cmd += f" -g {extra_output_file}"
    elif mode == 'timing':
        load_cmd += f" -t -l {extra_output_file}"
    print(run_command(load_cmd))


def get_unique_roots(roots_file_path: str) -> Set[str]:
    """ Loads the roots json object, expects to have a 'value' key
    Returns a set of root invocation after removing the trailing '_countX'
    """
    roots_list: List[str] = []
    with open(roots_file_path, 'r') as roots_file:
        roots_list = json.load(roots_file)['value']
    return set(map(lambda x: x.split('_count')[0], roots_list))


def union_json_dict(super_dict: Dict[str, Set],
    new_dict: Dict[str, List],
    call_graph: bool = False):
    # TODO: fix this to work with signatures as well
    # need to convert each dependency (which is list and not hashable) to tuple
    """ This function works with call graphs (and not yet signatures).
    Each key string in the new_dict is a function location followed by '_' and
    the number of that function invocations.
    The information on different invocations of the same function (location)
    are merged by adding the new information to a Set corresponding to that
    function location (used as key in the super_dict).
    In case this function is used on call_graphs, it removes _countX
    from the called invocations, before adding them to the set.
    super_dict is updated in place.
    """
    for loc_count in new_dict:
        location: str = loc_count[0: loc_count.rindex('_')]
        # super_dict keys are with out countXs
        if super_dict.get(location) == None:
            super_dict[location] = set()

        new_value_list: List = new_dict[loc_count]
        if len(new_value_list) > 0 and call_graph:
            for invocation in new_value_list:
                # remove the trailing _countXs
                callee: str = invocation[0: invocation.rindex('_')]
                super_dict[location].add(callee)
        else:
            # TODO: problem -> each element of new_value_list is a list
            super_dict[location].update(new_value_list)

def generate_roots(output_dir: str):
    """ Generates a super roots file (roots-nc.json) by doing a union of
    roots files generated from different execution paths.
    """
    if not os.path.isdir(join(output_dir, 'light')):
        light_instrument(input_dir, output_dir)
        print(f">>> [{page_name}] light instrumented!")

    roots_nc_file: str = join(output_dir, 'roots-nc.json')
    call_graph_nc_file: str = join(output_dir, 'call-graph-nc.json')
    if os.path.isfile(roots_nc_file) and os.path.isfile(call_graph_nc_file):
        return

    repeats: int = 0
    it: int = 0
    super_root_invocations: Set[str] = set()
    super_call_graph: Dict[str, List[str]] = {}
    while it < ITERATION_MAX:
        try:
            roots_file: str = join(output_dir, f"roots-{it}.json")
            cg_file: str = join(output_dir, f"call-graph-{it}.json")
            load_page(page_name, output_dir, 'light', roots_file, cg_file)
            super_root_invocations |= get_unique_roots(roots_file) # or .update

            it_call_graph: Dict = json.load(open(cg_file, 'r'))['value']
            union_json_dict(super_call_graph, it_call_graph, call_graph=True)

            # if has not thrown an exception then the root generation was fine
            it += 1
            repeats = 0
        except KeyError:
            # generated root file is not valid, retry this iteration
            repeats += 1
            if repeats < 3:
                print(f"Repeat generating roots-{it} and call-graph-{it}...")
            else:
                raise RuntimeError(f"Step 1 failed: repeated {repeats} times!")

    with open(roots_nc_file, 'w') as out_file:
        json.dump(list(super_root_invocations), out_file, indent=4)
    with open(call_graph_nc_file, 'w') as out_file:
        converted = {k: list(v) for k, v in super_call_graph.items()}
        json.dump(converted, out_file, indent=4)
    print(f">>> [{page_name}] generated super root and call graph!")


def generate_timings(output_dir: str):
    """ Generates a timing file (timing.json) using the super roots file
    of the last step.
    """
    if not os.path.isdir(join(output_dir, 'timing')):
        timing_instrument(input_dir, output_dir)
        print(f">>> [{page_name}] timing instrumented!")

    timing_file: str = join(output_dir, 'timing.json')
    plt_file: str = join(output_dir, 'plt-timing.json')
    if os.path.isfile(timing_file) and os.path.isfile(plt_file):
        with open(timing_file, 'r') as timing_file_handler:
            timings_info: Dict = json.load(timing_file_handler)
            if timings_info.get('value'):
                return
            else:
                print(f"Invalid timing.json file!")

    repeats: int = 0
    while repeats < 3:
        try:
            load_page(page_name, output_dir, 'timing', timing_file, plt_file)
            # check the validity of timing file
            timings_info: Dict = {}
            with open(timing_file, 'r') as timing_file_handler:
                timings_info = json.load(timing_file_handler)['value']
            print(f">>> [{page_name}] generated timing!")
            return
        except KeyError:
            repeats += 1
            print(f"Repeat generating timing ...")
    # if the function has not returned (up to this point) then it has failed!
    raise RuntimeError(f"Timing generation failed: repeated {repeats} times!")


def union_signatures(partial_union: Dict[str, List], new_sigs: Dict[str, List]):
    # combine the lists under the same key
    for key in new_sigs: # key is invocation_countX
        invoc_signature: List[List] = partial_union.get(key)
        if invoc_signature == None:
            partial_union[key] = new_sigs[key]
        else:
            invoc_signature.extend(new_sigs[key])


def generate_signatures(output_dir: str):
    """ Generates a super signature file (super-signature) by doing a union of
    signature files generated from different execution paths.
    """
    if not os.path.isdir(join(output_dir, 'heavy')):
        heavy_instrument(input_dir, output_dir)
        print(f">>> [{page_name}] heavy instrumented!")

    super_sig_file: str = join(output_dir, 'signature-super.json')
    if os.path.isfile(super_sig_file):
        with open(super_sig_file, 'r') as sig_file_handler:
            signatures: Dict = json.load(sig_file_handler)
            if signatures.get('value'):
                return
            else:
                print(f"Invalid super signature file!")

    repeats: int = 0
    it: int = 0
    # Union of signatures from 3 its
    # dictionary from invocation_countX to dependencies
    super_signatures: Dict[str, List] = {}
    while it < ITERATION_MAX:
        try:
            sig_file: str = join(output_dir, f'signature-{it}.json')
            load_page(page_name, output_dir, 'heavy', sig_file)
            # check the validity  of signature file
            with open(sig_file, 'r') as sig_file_handler:
                it_signatures: Dict = json.load(sig_file_handler)['value']
                old_len: int = len(super_signatures)
                union_signatures(super_signatures, it_signatures)
                print(f"Changed signature length: {old_len} -> {len(super_signatures)}")
            it += 1
            repeats = 0
        except KeyError:
            repeats += 1
            if repeats < 3:
                print(f"Repeat generating signature-{it} ...")
            else:
                raise RuntimeError(f"Signature generation failed: repeated {repeats} times!")

    # The generated JSON is expected to have a 'value' key
    expected_signature: Dict = {'type': 'object', 'value': super_signatures}
    with open(super_sig_file, 'w') as out_file:
        json.dump(expected_signature, out_file, indent = 4)
    print(f">>> [{page_name}] generated signature-super!")


def process_final_signatures(output_dir: str):
    final_signature: str = join(output_dir, 'signature-final.json')
    if os.path.isfile(final_signature):
        return
    roots: str = join(output_dir, 'roots-nc.json')
    timing: str = join(output_dir, 'timing.json')
    signature: str = join(output_dir, 'signature-super.json')
    process_cmd: str = "node ../scripts/process-root-signatures.js" \
                        f" -r {roots} -t {timing} -s {signature}" \
                        f" -o {final_signature}"
    run_command(process_cmd)
    print(f">>> [{page_name}] generated signature-final!")


def rewrite_page(input_dir: str, inter_dir: str, rewrite_dir: str):
    try:
        print(page_name)
        generate_roots(inter_dir)
        generate_timings(inter_dir)
        generate_signatures(inter_dir)
        process_final_signatures(inter_dir)
        rewrite_instrument(input_dir, inter_dir)
        copytree(join(inter_dir, 'rewrite'), rewrite_dir)
    except RuntimeError as e:
        print(f"[{page_name}] threw a runtime error while being rewritten: {e}")
    finally:
        print('-'*40)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(f"Usage: python3.9 {sys.argv[0]} input_dir output_dir")

    # input dir -- containing recorded mahimahi dirs
    input_abs_path: str = os.path.abspath(sys.argv[1])
    # rewrite dir -- containing the rewritten mahimahi dirs
    rewrite_abs_path: str = os.path.abspath(sys.argv[2])
    if not os.path.isdir(rewrite_abs_path):
        os.makedirs(rewrite_abs_path)
    # filter list -- only rewrite the pages that are listed
    filtered_list: List[str] = []
    if len(sys.argv) > 3:
        filtered_list = read_url_list(os.path.abspath(sys.argv[3]))

    # random seed used for assigning the port for loading the page
    seed(a = None)

    os.chdir(_INST_DIR)
    print('INFO: currently in:', os.getcwd())
    for page_name in os.listdir(input_abs_path):
        if len(filtered_list) != 0 and \
        not page_name in filtered_list:
                continue

        input_dir: str = join(input_abs_path, page_name)
        inter_dir: str = join(rewrite_abs_path, 'temp', page_name)
        rewrite_dir: str = join(rewrite_abs_path, page_name)

        # if input_dir is not a dir, skip it!
        if not os.path.isdir(input_dir):
            # print(f"{page_name} skipped: not a directory!")
            continue
        if os.path.isdir(rewrite_dir):
            rmtree(rewrite_dir)

        rewrite_page(input_dir, inter_dir, rewrite_dir)

