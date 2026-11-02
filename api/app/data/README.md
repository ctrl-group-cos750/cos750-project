# Data files

`common-passwords.txt`: the 10,000 most common passwords, lowercased and sorted, from
[SecLists](https://github.com/danielmiessler/SecLists/blob/master/Passwords/Common-Credentials/10k-most-common.txt)
(MIT License, Copyright (c) 2018 Daniel Miessler). New passwords on this list, or made of one of them plus
digits or symbols, are refused (`app/passwords.py`; NIST SP 800-63B §5.1.1.2).
