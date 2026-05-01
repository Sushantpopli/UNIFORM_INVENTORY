#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'uniform_project.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

# # SCHOOL UNIFORM SYSTEM — MASTER DATA

# ## Schools

# 1. Kali Devi School
# 2. DPS
# 3. Banda Bhadur School
# 4. SD Modern
# 5. Hindu School
# 6. EPS
# 7. Happy Public School
# 8. Bhagat Singh School

# ---

# ## Products

# Pant  
# Shirt  
# Nicker  
# Skirt  
# Divider  
# T-Shirt  
# Shoes  
# Socks  
# Tie  
# Belt (FREE SIZE)  
# Slax (Leggings)  
# Blazer  
# Jacket  
# Bag  
# Cap  
# House T-shirt  

# ---

# ## Sizes

# ### Pant

# 22  
# 24  
# 26  
# 28  
# 30  
# 32  
# 34  
# 36  
# 38  
# 40  
# 42  

# Special:

# 42-32  
# 42-34  
# 42-36  
# 42-38  
# 42-40  

# ---

# ### Shirt

# 24–52 (even numbers)

# ---

# ### Nicker

# 12  
# 13  
# 14  
# 15  
# 16  
# 17  
# 18  
# 20  

# (no 19)

# ---

# ### Socks

# 2  
# 3  
# 4  
# 5  
# 6  
# 7  

# ---

# ### Skirt

# 12  
# 14  
# 16  
# 18  
# 20  
# 22  
# 24  
# 26  

# ---

# ### Divider

# 18  
# 20  
# 22  
# 24  
# 26  

# ---

# ### T-Shirt

# 22–46 (even numbers)

# ---

# ### Shoes

# Small:

# 6–13  

# Big:

# 1B–10B  

# ---

# ### Tie

# 12  
# 14  
# 16  
# 56  

# ---

# ### Belt

# FREE SIZE ONLY

# ---

# ### Slax / Leggings

# 22–42 (even numbers)

# ---

# ## Important Rules

# - Belt is FREE SIZE  
# - Divider sizes fixed  
# - Pant 42 has waist variants  
# - No GST billing initially  
# - Returns allowed (size exchange)