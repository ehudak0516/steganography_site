from drafter import *
from dataclasses import dataclass
from typing import Optional
from PIL import Image
import io
import base64

END_MARKER="#####END#####"

set_website_title("Emma's test Website"),
set_site_information(
    author="Emma Hudak"
    description="This website allows users to encode a secret message in an image (PNG), then later allows then to decode the same image to find said message"
    sources"Drafter Docs",
    planning="",
    links=["https://github.com/ehudak0516/steganography_site"]
    )


@dataclass
class EncodeRecord:
    label:str
    message_length:int
    capacity_used:int #percent of the image's capacity used
    
    
@dataclass
class State:
    uploaded_image:str#was Optional[Image.Image]
    message:str
    capacity:int
    decoded_message:str
    error:str
    history:list[EncodeRecord]
    encoded_png:str
    
    
#------Helper Functions--------
    
def text_to_bits(text:str)->list[int]:
    """Convert text to a list of bits (8 per byte)."""
    bits=[]
    for byte in text.encode("utf-8"):
        for i in range(7,-1,-1):
            bits.append((byte>>i)&1)
    return bits


def calculate_capacity(img:Image.Image)->int:
    """Max message bytes the image can hold, minus the end marker."""
    width, height =img.size
    return(width * height * 3) // 8 - len(END_MARKER)


def encode_message(img:Image.Image, message:str)->bytes:
    """Hide the message in the least significant bits of each color value."""
    img=img.convert("RGB")
    bits=text_to_bits(message+END_MARKER)
    pixels=list(img.getdata())
    new_pixels=[]
    bit_index=0
    for(r,g,b) in pixels:
        channels=[r,g,b]
        for c in range(3):
            if bit_index<len(bits):
                channels[c]=(channels[c]&~1) | bits[bit_index]
                bit_index +=1
        new_pixels.append(tuple(channels))
    img.putdata(new_pixels)
    buffer=io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def decode_message(img:Image.Image)->str:
    """Read ISBs, group into bytes, stop at the end marker. Empty string if not found."""
    img=img.convert("RGB")
    data=bytearray()
    current=0
    count=0
    marker=END_MARKER.encode("utf-8")
    for (r,g,b) in img.getdata():
        for value in (r,g,b):
            current=(current << 1) | (value & 1)
            count += 1
            if count == 8:
                data.append(current)
                current=0
                count=0
                if data.endswith(marker):
                    return data[:-len(marker)].decode("utf-8", errors="replace")
    return""


#-----------routes--------------

@route
def index(state:State)->Page:
    return Page(state,[
        Header("Image Message Hider"),
        "Hide a secret message inside a PNG image, or reveal one.",
        Button("Encode a message", encode_page),
        Button("Decode an image", decode_page),
        Button("History", history_page),
        Button("How it works", how_it_works),
    ])


@route
def encode_page(state: State)-> Page:
    return Page(state, [
        Header("Encode"),
        "Upload a PNG and type the message to hide.",
        FileUpload("image_file", accept="image/png"),
        "Secret message:",
        TextArea("message",state.message),
        "Image label(shown in history):",
        TextBox("label",""),
        CheckBox("save_history", True),
        "Save this to my history",
        Button("Hide message",encode_result),
        Button("Home",index),
    ])


@route
def encode_result(state:State, image_file: bytes, message: str,
                  label:str, save_history: bool)-> Page:
    state.error=""
    state.encoded_png=""
    
    try:
        img=Image.open(io.BytesIO(image_file))
    except Exception:
        state.error="Could not read that file. Please upload a PNG."
        return Page(state, [Header("Encode Result"), state.error,
                            Button("Home", index)])
    
    #IF 1: file must be a PNG
    if img.format !="PNG":
        state.error="PNG only: JPG compression would destroy the hidden data."
        return Page(state, [Header("Encode Result"), state.error,
                            Button("Home", index)])
    
    state.uploaded_image=base64.b64encode(image_file).decode("ascii")
    state.capacity=calculate_capacity(img)
    state.message=message
    message_length=len(message.encode("utf-8"))
    
    #IF 2: message must fit
    if message_length> state.capacity:
        state.error=(f"Too long: your message is {message_length} characters, "
                     f"but this image holds {state.capacity}.")
        return Page(state, [Header("Encode Result"), state.error,
                            Button("Home", index)])
    
    state.encoded_png = base64.b64encode(encode_message(img, message)).decode("ascii")
    
    #IF 3: only save history if the checkbox is checked
    if save_history:
        percent=int(message_length * 100 / state.capacity) if state.capacity > 0 else 0
        name=label if label !="" else"Untitled"
        state.history.append(EncodeRecord(name, message_length, percent))
        
        state.message="" # clear after encoding
        
        return Page(state, [
            Header("Encode Result"),
            f"Message hidden! This image can hold {state.capacity} characters.",
            Download("Download encoded PNG", "encoded.png", base64.b64decode(state.encoded_png)),
            Button("Home",index),
        ])
    
    
@route
def decode_page(state: State)->Page:
    return Page(state, [
        Header("Decode"),
        "Upload a PNG that has a hidden message.",
        FileUpload("image_file", accept="image/png"),
        Button("Reveal message", decode_result),
        Button("Home", index),
    ])


@route
def decode_result(state:State, image_file: bytes)->Page:
    state.error=""
    state.decoded_message=""
    
    try:
        img=Image.open(io.BytesIO(image_file))
        state.uploaded_image=base64.b64encode(image_file).decode("ascii")
        state.decoded_message=decode_message(img)
    except Exception:
        state.error="Could not read that file. Please upload a PNG."
        
    #IF 4: decide what to show
    if state.error !="":
        result=state.error
    elif state.decoded_message=="":
         result="No hidden message was found in this image."
    else:
        result="Hidden message: "+state.decoded_message
            
    return Page(state, [
        Header("Decode Result"),
        result,
        Button("Home", index),
    ])
    
    
@route
def history_page(state:State)->Page:
    content=[Header("Encoding History")]
    if len(state.history)==0:
        content.append("No encodings saved yet.")
        
        #LOOP over the list of EncodeRecord instances
    for record in state.history:
        content.append(f"{record.label}: {record.message_length} characters"
                        f"({record.capacity_used}% of capacity used)")
            
    content.append(Button("Home", index))
    return Page(state, content)
        
        
@route
def how_it_works(state:State)->Page:
    return Page(state, [
        Header("How It Works"),
        "Every pixel has red, green, and blue values (0-255).",
        "LSB steganography changes only the last bit of each value, which is invisible to the eye. ",
        "Each character becomes 8 bits, and each bit replaces one last bit. "
        "An end marker tells the decoder where to stop. ",
        "Images must stay PNG: JPG compression would change the pixels and destroy the message.",
        Button("Home", index),
    ])


start_server(State("", "",0,"","",[], ""))
    
    

