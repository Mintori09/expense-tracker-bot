{
  pkgs ? import <nixpkgs> { },
}:

pkgs.mkShell {
  nativeBuildInputs = with pkgs; [
    tesseract
    tesseract-lang
    poppler_utils
  ];

  shellHook = ''
    export TESSDATA_PREFIX="${pkgs.tesseract}/share/tessdata"
    echo "Tesseract OCR ready with English and Vietnamese language packs"
  '';
}
