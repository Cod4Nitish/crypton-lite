"""Writes docs/sample/event-agenda.pdf: a real 2-page text PDF for the RAG demo/tests.

Hand-rolled PDF (Helvetica, one text stream per page) so no PDF library is needed.
Content is the public agenda of the Speed of Thought meetup (luma.com/sot).
"""
import os
import sys

PAGES = [
    [
        ("Speed of Thought: AI Meetup - Event Agenda", 16),
        ("Hosted by WeMakeDevs. Venue: 91Springboard, 21B Udyog Vihar, Sector 18, Gurugram.", 10),
        ("Date: Saturday 31 October 2026. Capacity 100 attendees, in person only.", 10),
        ("", 10),
        ("09:00 - 09:30  Check-in, welcome drinks and networking. Bring your ID and laptop charger.", 10),
        ("09:30 - 10:00  Technical talk: Why Model Quantization Matters for Efficient Inference,", 10),
        ("               by Shivay. Covers Q4 and Q8 formats, memory bandwidth and accuracy trade-offs.", 10),
        ("10:00 - 10:40  Hands-on workshop: Build Faster with Wispr Flow. Install Wispr Flow", 10),
        ("               beforehand and grant microphone permission.", 10),
        ("10:40          Building phase starts. Teams build an AI project on site.", 10),
    ],
    [
        ("Agenda (continued) and submission rules", 14),
        ("13:00 - 14:00  Pizza lunch and drinks. Building continues.", 10),
        ("14:00          Build submissions close. Late submissions are not accepted.", 10),
        ("               Submit a public repo link and a short demo video or live demo.", 10),
        ("14:00 - 14:45  Networking and judging. Each team gets about two minutes to demo.", 10),
        ("14:45 - 15:00  Winner announcement, prizes and closing remarks.", 10),
        ("", 10),
        ("Prizes: best build wins a Keychron keyboard. Best social media post about the", 10),
        ("meetup wins a Logitech MX Master 4. Wispr Flow swag for participants.", 10),
    ],
]


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build(path: str) -> None:
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for lines in PAGES:
        y, ops = 790, ["BT"]
        for text, size in lines:
            ops.append(f"/F1 {size} Tf 1 0 0 1 50 {y} Tm ({_esc(text)}) Tj")
            y -= size + 10
        ops.append("ET")
        stream = "\n".join(ops)
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        content_id = len(objs)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(out)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "docs", "sample", "event-agenda.pdf")
    build(target)
    print("wrote", os.path.abspath(target))
