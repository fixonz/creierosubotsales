import qrcode
import io
from aiogram.types import BufferedInputFile

def generate_ltc_qr(address: str, amount: float = None) -> BufferedInputFile:
    """
    Generates a QR code for a Litecoin address and optional amount.
    Returns an aiogram BufferedInputFile.
    """
    if amount:
        data = f"litecoin:{address}?amount={amount}"
    else:
        data = f"litecoin:{address}"
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to bytes
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return BufferedInputFile(img_byte_arr.getvalue(), filename="payment_qr.png")
