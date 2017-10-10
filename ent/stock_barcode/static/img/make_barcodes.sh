#!/bin/sh

barcode -t 2x7+40+40 -m 50x30 -p "210x297mm" -e code128b  << BARCODES | ps2pdf - - > barcodes_actions.pdf
O-CMD.MAIN-MENU
O-CMD.SAVE
O-CMD.DISCARD
O-CMD.EDIT
O-BTN.validate
O-BTN.cancel
O-BTN.print-op
O-BTN.print-slip
O-BTN.pack
O-BTN.scrap
O-CMD.PREV
O-CMD.NEXT
O-CMD.PAGER-FIRST
O-CMD.PAGER-LAST
BARCODES

barcode -t 2x7+40+40 -m 50x30 -p "210x297mm" -e code128b > barcodes_demo_barcode.ps  << BARCODES
054398267125
204539674215
420196872340
601647855631
LOC-01-00-00
LOC-01-01-00
LOC-01-01-01
LOC-01-02-00
LOC-02-00-00
PACK0000001
WH/OUT/00005
WH/IN/00003
LOT-000001
LOT-000002
BARCODES

cat > barcodes_demo_header.ps << HEADER
/showTitle { /Helvetica findfont 12 scalefont setfont moveto show } def
(iPad Mini) 89 705 showTitle
(USB Adapter) 348 705 showTitle
(Processor Core i5 2.70Ghz) 89 596 showTitle
(Ice Cream) 348 596 showTitle
(WH/Stock) 89 487 showTitle
(WH/Stock/Shelf 1) 348 487 showTitle
(WH/Stock/Shelf 1/Small Refrigerator) 89 378 showTitle
(WH/Stock/Shelf 2) 348 378 showTitle
(Chick/Stock) 89 270 showTitle
HEADER

cat barcodes_demo_header.ps barcodes_demo_barcode.ps | ps2pdf - - > barcodes_demo.pdf
rm barcodes_demo_header.ps barcodes_demo_barcode.ps 
