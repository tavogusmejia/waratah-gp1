Replacement pictures for the register.

Drop a file here named after the item, and the extractor uses it instead of
whatever it would have picked out of the PDF itself. See PICTURE-AUDIT.md in
the folder above for the list of which items need one and what to call the
file.

  - Name it with the datasheet's slug, e.g. f1-robert-mfg-bob-r400-brass-float-valve.jpg
    The item code works too (A1.jpg), but three plumbing items all carry the
    code J9, so a file named J9.jpg would apply to all three.
  - .jpg, .jpeg, .png and .webp are all read.
  - A cutout on a plain white ground looks best: the register composites these
    onto a light tile with multiply blending.

Then run:  python tools/extract_datasheets.py
