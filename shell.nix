let
  pkgs = import (builtins.fetchTarball {
    url = "https://github.com/NixOS/nixpkgs/archive/21a67dc470149f337cecafbe965d8d252a390518.tar.gz";
    sha256 = "sha256-ugpsyk3NM2s87vXfUiIIiibbJ4Pp0JPS5p/3mfs+q+c=";
  }) { };
in
pkgs.mkShell {
  packages = [ pkgs.python314 pkgs.uv pkgs.gnumake ];
  env.UV_PYTHON = "${pkgs.python314}/bin/python";
  env.UV_PYTHON_DOWNLOADS = "never";
  shellHook = ''
    unset VIRTUAL_ENV
    export UV_CACHE_DIR="$PWD/.cache/uv"
  '';
}
