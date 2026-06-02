# Homebrew formula for the AIMA Labs CLI.
#
# This file belongs in a tap repo (e.g. github.com/aimalabs/homebrew-tap) so
# users can `brew install aimalabs/tap/aima`. It is kept here as the canonical
# source.
#
# Releasing a new version:
#   1. Publish the new version to PyPI (the Release workflow does this).
#   2. Bump `url` + `sha256` below to the new sdist (sha256 from PyPI's
#      "Download files" page, or `brew fetch`).
#   3. Regenerate the dependency `resource` blocks:
#        brew install brew-pip-audit  # one-time, optional
#        brew update-python-resources Formula/aima.rb
#   4. Open a PR against the tap repo; CI runs `brew test-bot`.
class Aima < Formula
  include Language::Python::Virtualenv

  desc "AWS-CLI-shaped command line for AIMA Labs voice/WhatsApp campaigns"
  homepage "https://aimalabs.io"
  url "https://files.pythonhosted.org/packages/source/a/aimalabs-cli/aimalabs_cli-0.1.0.tar.gz"
  sha256 "REPLACE_WITH_SDIST_SHA256"
  license "MIT"

  depends_on "python@3.12"

  # `brew update-python-resources` regenerates the resource blocks below for
  # typer, click, httpx, rich, pyyaml and their transitive dependencies.
  # resource "..." do ... end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "aima #{version}", shell_output("#{bin}/aima --version")
  end
end
