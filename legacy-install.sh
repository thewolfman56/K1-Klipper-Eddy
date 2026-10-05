#!/bin/sh
# Legacy upstream installer entry point.
#
# The original fork installed its Klipper/config tree directly. It is retained
# only to make the repository history and older instructions easier to follow.
# For K1 Max + CFS + Eddy Duo on CrealityOS 2.3.5.33 use:
#
#   sh install.sh doctor
#   sh install.sh stage ...
#
# This wrapper intentionally does not perform the old blind overwrite.
echo "Legacy installer disabled in this K1 Max+CFS branch."
echo "Use: sh install.sh doctor"
exit 2
