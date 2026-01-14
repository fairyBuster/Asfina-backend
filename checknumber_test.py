import os
import sys
import django


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()


from accounts.utils import check_whatsapp_registered


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("phone", help="Phone number, e.g. 0813xxxxxxx")
    args = parser.parse_args()

    ok, msg = check_whatsapp_registered(args.phone)
    status = "OK" if ok else "FAIL"
    print(f"{status}: {msg}")


if __name__ == "__main__":
    main()

