from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
from django.core.files import File
from .models import Payment, Allowed_User
import base64
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from pathlib import Path
from datetime import datetime, timezone, timedelta
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader
import string, random, os, stripe
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.http import FileResponse, Http404
# from ipware import get_client_ip
from cryptography.fernet import Fernet
from django.utils import timezone

BASE_DIR = Path(__file__).resolve().parent.parent

stripe.api_key = settings.STRIPE_KEY

# Register the Calibri font
pdfmetrics.registerFont(TTFont('Calibri', settings.CALIBRI))
pdfmetrics.registerFont(TTFont('Calibri-Italic', settings.CALIBRII))


@staff_member_required
def serve_protected_media(request, path):
    media_root = settings.MEDIA_ROOT
    file_path = Path(media_root) / path

    if not file_path.exists():
        raise Http404("File does not exist")

    response = FileResponse(open(file_path, 'rb'))
    response['Content-Disposition'] = 'inline; filename="%s"' % file_path.name
    return response


def get_unique_filename(directory, filename):
    """
    Generate a unique filename by appending a number if the file already exists in the specified directory.
    """
    directory = BASE_DIR / directory
    characters = string.ascii_letters + string.digits
    base, extension = os.path.splitext(filename)
    new_filename = filename
    new_filepath = os.path.join(directory, new_filename)

    while os.path.exists(new_filepath):
        new_filename = f"{base}_{''.join(random.choice(characters) for _ in range(5))}{extension}"
        new_filepath = os.path.join(directory, new_filename)

    return new_filepath


def check_link(link, email):
    try:
        user = Allowed_User.objects.get(Email_ID=email.lower())

        fernet = Fernet(os.getenv('LINK_KEY'))

        if user.Email_ID != fernet.decrypt(link.encode()).decode('utf-8'):
            msg = "Authentication error with link and email"
            return msg

        if user.Expire_Date <= timezone.localdate():
            msg = "Link Expired"
            return msg

        return ""
    except Allowed_User.DoesNotExist:
        return "Authentication error with link and email"
    except Exception as e:
        print("Check link Exception:",e)
        return "Error 404"


def pdf_changes(path, input_file, changes, audit=None, initials=None):
    input_pdf_path = input_file
    output_pdf_path = get_unique_filename(path, os.path.basename(input_file))
    pdf_reader = PdfReader(input_pdf_path)
    pdf_writer = PdfWriter()

    for page_num in range(len(pdf_reader.pages)):
        page = pdf_reader.pages[page_num]

        try:

            packet = BytesIO()
            can = canvas.Canvas(packet, pagesize=(page.mediabox.right, page.mediabox.top))
            if page_num in changes:
                if changes[page_num]:
                    if changes[page_num]["type"] == "string":
                        for change in changes[page_num]["changes"]:
                            can.setFont("Calibri-Italic", 12)
                            can.drawString(change['x'], change['y'], change['data'])

                    elif changes[page_num]["type"] == "image":

                        changes[page_num]["changes"] = changes[page_num]["changes"][0]

                        base64_signature = changes[page_num]["changes"]['data']
                        base64_signature = base64_signature.split(",")[1]

                        # Decode the base64 string and open the image
                        signature_data = base64.b64decode(base64_signature)
                        signature_image = Image.open(BytesIO(signature_data))

                        signature_image = signature_image.convert("RGBA")
                        canvas_image = Image.new("RGBA", signature_image.size,
                                                 (255, 255, 255, 0))  # Create a transparent background
                        canvas_image.paste(signature_image, (0, 0), signature_image)
                        canvas_image = canvas_image.convert("RGB")  # Convert back to RGB
                        signature_image = ImageReader(canvas_image)
                        can.drawImage(signature_image, changes[page_num]["changes"]['x'],
                                      changes[page_num]["changes"]['y'],
                                      width=signature_image.getSize()[0] * 0.3,
                                      height=signature_image.getSize()[1] * 0.3)
            if initials:
                can.setFont("Calibri", 12)
                can.drawString(560, 20, initials)

            can.save()
            packet.seek(0)
            new_pdf = PdfReader(packet)
            new_page = new_pdf.pages[0]
            page.merge_page(new_page)

        except Exception as e:
            pass

        pdf_writer.add_page(page)

    if audit is not None:
        audit_pdf = PdfReader(os.path.join(BASE_DIR, f"App/Audit.pdf"))
        audit_page = audit_pdf.pages[0]
        packet = BytesIO()
        c = canvas.Canvas(packet, pagesize=(audit_page.mediabox.right, audit_page.mediabox.top))
        for index, value in enumerate(audit[::-1]):
            c.setFont("Calibri-Italic", 12)
            c.drawString(230, 500 + (index * 30), value)

        c.save()
        packet.seek(0)
        new_pdf = PdfReader(packet)
        new_page = new_pdf.pages[0]
        audit_page.merge_page(new_page)

        pdf_writer.add_page(audit_page)

    with open(output_pdf_path, "wb") as output_pdf_file:
        pdf_writer.write(output_pdf_file)

    return os.path.basename(output_pdf_path)


def step1(request, link):
    request.session.flush()
    return render(request, "step1.html", {"link": link})


def step2(request, link):
    if request.method == "POST":
        try:
            msg = check_link(link, request.POST['email'])
            if msg != "":
                raise Exception

        except Exception as e:
            print("Link Error", e)
            return HttpResponse(msg)

        try:
            if os.path.exists(BASE_DIR / "Documents" / request.session["step1_file"]):
                os.remove(BASE_DIR / "Documents" / request.session["step1_file"])
                del request.session["step1_file"]
        except Exception as e:
            pass
        try:
            full_name = request.POST["Full Name"]
            SSN = request.POST["SSN Number"]
            address = request.POST["Address"]
            changes = {
                0: {
                    "type": "string",
                    "changes": [
                        {"x": 390,
                         "y": 552,
                         "data": full_name
                         },
                        {"x": 310,
                         "y": 536,
                         "data": SSN
                         },
                        {"x": 196,
                         "y": 568,
                         "data": datetime.now().strftime("%m-%d-%Y")
                         }
                    ]
                },
                7: {
                    "type": "string",
                    "changes": [
                        {"x": 345,
                         "y": 218,
                         "data": full_name
                         },
                        {"x": 340,
                         "y": 192,
                         "data": datetime.now().strftime("%m-%d-%Y")
                         }
                    ]
                }
            }
            step1_file = pdf_changes("Documents", os.path.join(BASE_DIR, "App/AI_Definitve_Non_Compete_Agreement.pdf"), changes)
            request.session["step1_file"] = step1_file
            request.session["email"] = request.POST['email']
            request.session["phno"] = request.POST['Phone Number']
            request.session["name"] = full_name
            request.session["ssn"] = SSN
            request.session["Address"] = address

            return render(request, "step2.html", {"name": full_name, "SSN": SSN, "Address": address, "link": link,
                                                  'adobe_id': settings.ADOBE_ID})
        except Exception as e:
            print(e)
            return redirect('/step1/' + link + '/')

    return redirect('/step1/' + link + '/')


def step3(request, link):
    if request.method == "POST":

        try:
            msg = check_link(link, request.session["email"])
            if msg != "":
                raise Exception

        except Exception as e:
            print("Link Error", e)
            return HttpResponse(msg)

        try:
            if os.path.exists(BASE_DIR / "Documents" / request.session["step2_file"]):
                os.remove(BASE_DIR / "Documents" / request.session["step2_file"])
                del request.session["step2_file"]
        except Exception as e:
            pass
        try:
            full_name = request.session["name"]
            SSN = request.POST["SSN Number"]
            address = request.POST["Address"]
            changes = {
                0: {
                    "type": "string",
                    "changes": [
                        {"x": 100,
                         "y": 583,
                         "data": datetime.now().strftime("%m-%d-%Y")
                         }
                    ]
                },
                1: {
                    "type": "string",
                    "changes": [
                        {"x": 208,
                         "y": 504,
                         "data": datetime.now().strftime("%m-%d-%Y")
                         },
                        {"x": 260,
                         "y": 473,
                         "data": request.session["name"]
                         },
                        {"x": 180,
                         "y": 456,
                         "data": request.session["ssn"]
                         }
                    ]
                },
                3: {
                    "type": "string",
                    "changes": [
                        {"x": 75,
                         "y": 545,
                         "data": request.session["name"]
                         },
                        {"x": 75,
                         "y": 493,
                         "data": request.session["Address"]
                         }
                    ]
                }
            }
            step2_file = pdf_changes("Documents", os.path.join(BASE_DIR, "App/AI_Definitive_Promissory_Note.pdf"), changes)
            request.session["step2_file"] = step2_file

            request.session["sign1"] = request.POST["sign"]

            now = datetime.now()
            timestamp = now.strftime('%a %b %d %Y %H:%M:%S EST%z ')
            request.session["sign1_time"] = timestamp

            if "sign1" in request.session:
                request.session.modified = True

            return render(request, "step3.html", {"link": link, 'adobe_id': settings.ADOBE_ID})
        except Exception as e:
            print(e)
            return redirect('/step1/' + link + '/')

    return redirect('/step1/' + link + '/')


def step4(request, link):
    if request.method == "POST":

        try:
            msg = check_link(link, request.session["email"])
            if msg != "":
                raise Exception

        except Exception as e:
            print("Link Error", e)
            return HttpResponse(msg)

        try:
            request.session["sign2"] = request.POST["sign"]
            now = datetime.now()
            timestamp = now.strftime('%a %b %d %Y %H:%M:%S EST%z')
            request.session["sign2_time"] = timestamp
            request.session["initials"] = request.POST["Initials"]

            if "sign2" in request.session:
                request.session.modified = True

            return redirect(os.getenv('PAYMENT_LINK'))
        except Exception as e:
            print(e)
            return redirect('/step1/' + link + '/')

    return redirect('/step1/' + link + '/')

def get_client_ip(request):
    try:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        print("HTTP_X_FORWARDED_FOR:", request.META.get('HTTP_X_FORWARDED_FOR'))
        print("REMOTE_ADDR:", request.META.get('REMOTE_ADDR'))
        return ip
    except Exception as e:
        return "Unable to get IP"

def payment_completed(request):
    try:

        checkout_session = stripe.checkout.Session.retrieve(request.GET['session_id'])
        payment_intent_id = checkout_session.payment_intent

        try:
            user = Allowed_User.objects.get(Email_ID=request.session["email"].lower())
            user.delete()
        except Exception as e:
            print(e)

        if payment_intent_id:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            changes = {
                7: {
                    "type": "image",
                    "changes": [
                        {"x": 360,
                         "y": 233,
                         "data": request.session['sign1']
                         }
                    ]
                }
            }

            ip_address = get_client_ip(request)

            audit_details = [
                request.session["name"],
                request.session["email"],
                request.session["phno"],
                request.session["sign1_time"],
                payment_intent.id,
                ip_address
            ]

            step1_file = pdf_changes("Documents", os.path.join(BASE_DIR, f"Documents/{request.session['step1_file']}"), changes,
                                     audit=audit_details, initials=request.session["initials"])
            os.remove(os.path.join(BASE_DIR, f"Documents/{request.session['step1_file']}"))

            changes = {
                3: {
                    "type": "image",
                    "changes": [
                        {"x": 73,
                         "y": 593,
                         "data": request.session['sign2']
                         }
                    ]
                }
            }

            audit_details[3] = request.session["sign2_time"]

            step2_file = pdf_changes("Documents", os.path.join(BASE_DIR, f"Documents/{request.session['step2_file']}"), changes,
                                     audit=audit_details, initials=request.session["initials"])
            os.remove(BASE_DIR / 'Documents' / request.session['step2_file'])

            with open(BASE_DIR / 'Documents' / step1_file, 'rb') as f1, open(BASE_DIR / 'Documents' / step2_file,
                                                                             'rb') as f2:

                # Save to the database
                payment = Payment(Payment_ID=payment_intent.id,
                                  Payment_Details=checkout_session.customer_details,
                                  Non_Compete_Document=File(f1, name=step1_file),
                                  Promissory_Document=File(f2, name=step2_file))

                payment.save()

            os.remove(BASE_DIR / 'Documents' / step1_file)
            os.remove(BASE_DIR / 'Documents' / step2_file)

            request.session.flush()
            return render(request, 'success.html', {'pid': payment_intent.id})
        else:
            return HttpResponse("No payment intent found for this checkout session.")
    except OSError as e:
        print(e)
        checkout_session = stripe.checkout.Session.retrieve(request.GET['stripe'])
        payment_intent_id = checkout_session.payment_intent
        if payment_intent_id:
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            payment = Payment(Payment_ID=payment_intent.id,
                              Payment_Details=checkout_session.customer_details)
            payment.save()
            request.session.flush()
            return render(request, 'success.html', {'pid': payment_intent.id})

        else:
            return HttpResponse("No payment intent found for this checkout session.")

    except stripe.error.StripeError as e:
        print(f"Error retrieving checkout session or payment intent: {e}")
        return HttpResponse("Error")

    except Exception as e:
        print("Payment Exception:",e)
        return HttpResponse("Invalid Request")


def test(request):
    return render(request, 'success.html', {'pid': 'kakjhwsdsljkebnfkh'})
