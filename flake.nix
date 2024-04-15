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
            packages = [
              pkgs.python310
              pkgs.poetry
            ];

            LD_LIBRARY_PATH = lib.optional stdenv.isLinux (pkgs.lib.makeLibraryPath [
              pkgs.stdenv.cc.cc
            ]);

            # Put the venv on the repo, so direnv can access it
            POETRY_VIRTUALENVS_IN_PROJECT = "true";
            POETRY_VIRTUALENVS_PATH = "{project-dir}/.venv";

            # Use python from path, so you can use a different version to the one bundled with poetry
            POETRY_VIRTUALENVS_PREFER_ACTIVE_PYTHON = "true";

            # Use ipdb
            PYTHONBREAKPOINT = "ipdb.set_trace";
          };
      }
    );
}
