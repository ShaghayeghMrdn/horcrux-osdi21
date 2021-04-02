# Horcrux

## VM User and password:

The username and password of this VM are *test* and *test*.

## Getting Started:

All Horcrux source code are placed under *~/Projects/horcrux-osdi21*.

Horcrux uses [Mahimahi](http://mahimahi.mit.edu/), a lightweight tool for recording and replaying HTTP traffic.
The version of [Mahimahi](https://github.com/ShaghayeghMrdn/mahimahi/tree/ubuntu_16_04) used in our experiments is already cloned and installed on this VM under *~/Projects/mahimahi*.

Horcrux rewriter takes a set of recorded mahimahi directories as input and returns a set of rewritten mahimahi directories for each given page in the input set.

All mahimahi recorded pages used in our experiments are placed in 3 directories inside root directory:

1. __kick-the-tires__: only one recorded mahimahi directory (`www.cbsnews.com`) as a "Hello world" type of example.

2. __more-examples__: a set of selected pages to demonstrate Horcrux functionality without spending several hours that it would take to run Horcrux on the whole corpus.

3. __all-pages__: the complete set of pages considered in our experiments.


## Startup:

Navigate to Horcrux root directory: `cd ~/Projects/horcrux-osdi21`

Each time VM is started, run the `sudo ./startup.sh`.
If the startup script is not executed as the first step, you might see an error as below when Horcrux is used:

> Died on std::runtime_error: mm-webreplay: Please run "sudo sysctl -w net.ipv4.ip_forward=1" to enable IP forwarding.


## Kick-the-tires:

The main script to run the server-side operations (as described in section 4.1 of paper) is *rewrite_pages.py*.

*rewrite_pages.py* takes two input arguments: 1) an input directory containing the recorded mahimahi dirs (e.g., one of the 3 directories mentioned above). 2) an output directory which will contain rewritten mahimahi dirs.

For example:

> python3.9 rewrite_pages.py kick-the-tires output

generates an *output* directory containing a rewritten mahimahi directory named `www.cbsnews.com`. The top-level HTML includes Horcrux dynamic scheduler code. Also, each frame is rewritten to include the function signatures and a call to Horcrux scheduler. Please refer to section 4.2 of the paper for more details.

Next, you can use *load_a_page.sh* script  to load a page (i.e., reply its mahimahi directory) in chrome and see the results visually.

To load the rewritten page:
> ./load_a_page.sh output/www.cbsnews.com

To load the original (recorded) version of the page:
> ./load_a_page.sh kick-the-tires/www.cbsnews.com

The script starts a chrome instance, loads the page, and keep the chrome alive until you close it manually. It also prints the page load time in the standard output. If you would like the chrome instance to be killed after the page is loaded, you can remove *-a* option from the last line of the script.

By comparing the page load times of the recorded page and the rewritten one, you can see that Horcrux improves the page load time among other metrics.

#### Note 1:
Once a page is loaded in chrome, it is expected to see the following message:
> You are using an unsupported command-line flag: --disable-setuid-sandbox. Stability and security will suffer.

This unsupported flag is not set by us, instead the chrome-launcher sets it by default on Linux platforms. You can ignore the message.

#### Note 2:
Both *rewrite_pages.py* and *load_a_page.sh* scripts are supposed to be executed from the root directory, as they are dependent of other sub-modules and scripts placed next to them.


## More Examples:
