from django.core.management.base import BaseCommand
from deposits.models import GatewaySettings


class Command(BaseCommand):
    help = 'Seed default gateway settings for Klikpay and Jayapay'

    def handle(self, *args, **options):
        # Provided seed values
        klikpay_public_key = 'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQClCcqIoPbJutG+d/JYQ6se5BnaO8Tapm7ssZDCYZgkEWhsaydRmRivC1okBOFOlASN6W20ESkt7X5Z8aWyrkLpKqrJ6ixCef0f/O4z7/PaKGeCh7egNpMSNL9XApIf+HU+co+hJc59TN424KRKY2HfnQh8qpOd/BqXYcd/JoiUHwIDAQAB'
        klikpay_private_key = 'MIICdgIBADANBgkqhkiG9w0BAQEFAASCAmAwggJcAgEAAoGBALI1GyfyI6AVyokJq04SLdoK3MxuaGwtzfm5cSXVUP+cM2K0/RbyflWx0r+G9ScCPYyqQuOEYdQvs1SH402JtYDuXjbNCczUsURao0rKx1mF0OyT8XpWXIlajI11Q7uJue1auY2iG6BaAD7mUXIOT5/nQu+XXelWRUAFdfER8m0NAgMBAAECgYBIWidcYIL2S+KfIL3cRKU5EY/zsB/VTAOEkDXQFnt8S/7Q5Iqc9nc0c64M9M4zuEUlBzuBBA50B6nXeBRhNrfporrKphiUkyhukeBrFLiCLhVJq/C7biOdR4bPhheTT3G0vduGYo5aF/ZLhdxDBDVkKL40LQ6BzBbYg2d23Lp8AQJBAOmib/vpXS54gapq4kKRF6EEHZSg+gXR8b5GAenmtdcXwZnBKMAYSYNkeF4z/Q37DTKLMWHHEemGMHQlDtOYAHECQQDDRFhvMM4OAVNyCfK4NM447sEhiu1QZYl+rhP2vodmih2/4+EhPHuRo+aWgqnMN9wnEknglto/Z7u59LrLgIRdAkEAqM5tCx657PG0/mTrxhz/bZ+Dn/gPrlTazhfXGiFQEXFguK8PunvR4dWeArKdjJRwHKzlqTgkgQ4rxD9iTw/sgQJAWpamgE8gCRdMYyeCVzsIQRlit/D/z8CLdR3dXSdfIY8J5jAODaFFondrToAnzfpMREQTygGyFqBFUyvaTPa+cQJAQWFEM6IMAjgtaiMsQT77TSkrpZUqnbw5eFX2B31L98jfz+h9CbuLxbukTWe4N3OYMK6/OOadJj7ihfYMxCgeRg=='
        klikpay_merchant_code = 'S820240925150637000035'
        klikpay_api_url = 'https://idvs.klysnv.com/gateway/prepaidOrder'

        jayapay_public_key = 'MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCjnWL5methO8aMhxKGnLn4TPjBJdxJcJCFDezy0DPEa1X2xcFdKyfyNC67bod/jcCw3QiEsXFyjmg+nBhPxBzdspI0WUyVj5NNgPqDxLKP8afvAUzQLk+nBUArON8L923IaXJAN/eNrl0T7PMYVENHCZeGOfGdEtSCXy2SkCN4FwIDAQAB'
        jayapay_private_key = 'MIICdgIBADANBgkqhkiG9w0BAQEFAASCAmAwggJcAgEAAoGBAJosLlDBmxO2aOPy6L2VKDM10lkJBi+liEi4lgkA2CwTdo3ni2MhhVIJsycr2Onos0HWut2gZstci7WDm8vdO1GJHIFSdauNSbueLznzGnnj8Zqt/mkv1J5XPSbjNgXMMgImiHVGOVdzORY6PKHNEWVJjVv4cucPqBQ5DSLViCoPAgMBAAECgYAPgsloG4pgGdaEtIAg7rw8JrqSdZt3OLa05klF/51AFfc0AKsf3pP8tHgfRUSOB/jc818ahBRDenyd1u9aO9hHTDG97ntiO9UyFwDFtl11dBSI3eDtYdXmyiVtB65yzPYdCxuZiaDTIKKWVj8tBqpyPwuRaJRHG6A5xrIkL+BvlQJBANLkO4QrLT4rskXQt9t+bImfal0YP0sobB4tcH3AdnGmPz3ATwYPAs+bfew1yZ0XWUz2fYjc8rTiO7fJ4F2kkGsCQQC7JjG5WfoFIwxOw9r6smdUsRTybHjz0r7jWCe5wGXkEkY17Hwp+0hpE6+HfSgPEpuV3NXZfwU6b+htO04JrSXtAkB53/ANN66TyUjjU/WM4Yj0F66uUj7xvlCNOBFUew94Km1N0H9arv4e4GtrQMJdCItREPoHSDjzE/MTCZWiSGI1AkEAgasVCLeu46BFBs3tC4ZQ0f1f5hgCNe3vFNYfsDP+ZOfEfdg8r1nL8gIRvG6bMtZRtqQsB2Za2QJwqD5O86VkgQJALnUdSUH2dziMGHo+kwt/tbAgEZqYqjr7mHidAs7uugkEPG1U0Jb4TuA9a+xn68ka1a0nRz6kqf4w48Nlfg8AKg=='
        jayapay_merchant_code = 'S820250926154015000114'
        jayapay_api_url = 'https://openapi.jayapayment.com/gateway/prepaidOrder'

        # Domain harus diisi manual di admin jika belum ada
        gs, created = GatewaySettings.objects.get_or_create(id=1)
        gs.default_wallet_type = 'BALANCE'
        gs.jayapay_enabled = True
        gs.klikpay_enabled = True

        # Klikpay
        gs.klikpay_public_key = klikpay_public_key
        gs.klikpay_private_key = klikpay_private_key
        gs.klikpay_merchant_code = klikpay_merchant_code
        gs.klikpay_api_url = klikpay_api_url
        # Gunakan endpoint callback statis agar konsisten dengan konfigurasi views
        gs.klikpay_callback_path = "api/deposits/klikpay/callback/"
        gs.klikpay_redirect_url = gs.klikpay_redirect_url or ''

        # Jayapay
        gs.jayapay_public_key = jayapay_public_key
        gs.jayapay_private_key = jayapay_private_key
        gs.jayapay_merchant_code = jayapay_merchant_code
        gs.jayapay_api_url = jayapay_api_url
        gs.jayapay_callback_path = "api/deposits/jayapay/callback/"
        gs.jayapay_redirect_url = gs.jayapay_redirect_url or ''

        gs.save()
        self.stdout.write(self.style.SUCCESS('Gateway settings seeded. Fill app_domain and redirect URLs in admin if needed.'))