{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };
  outputs = {nixpkgs, ...}: let
    inherit (nixpkgs) lib;
    withSystem = f:
      lib.fold lib.recursiveUpdate {}
      (map f ["x86_64-linux" "x86_64-darwin" "aarch64-linux" "aarch64-darwin"]);
  in
    withSystem (
      system: let
        pkgs = nixpkgs.legacyPackages.${system};
        inherit (pkgs) lib stdenv;
      in {
        devShells.${system}.default =
          pkgs.mkShell
          {
            packages = with pkgs; [
              python310
              uv
            ];

            LD_LIBRARY_PATH = lib.optional stdenv.isLinux (pkgs.lib.makeLibraryPath [
              pkgs.stdenv.cc.cc
            ]);

            # Use ipdb
            PYTHONBREAKPOINT = "ipdb.set_trace";

            shellHook = ''
              if [ ! -d .venv ]; then
                uv venv
                uv pip install -e .
              fi
              source .venv/bin/activate
            '';
          };
      }
    );
}
