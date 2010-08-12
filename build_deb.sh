#!/bin/bash

REVNO=$(bzr revno)
VERSION="0.2~bzr$REVNO"

# Delete and regenerate debian/changelog
# Yes, I know there are Debian people who would kill me for this,
# but it's ridiculous to keep a changelog in a file tracked by bzr
# All I want is a package with a specific version number! PPA updates
# don't even show changelog info.

cat >debian/changelog <<EOF
pithos ($VERSION) lucid; urgency=low

  * Build from bzr r$REVNO

 -- Kevin Mehall <km@kevinmehall.net>  $(date -R)
EOF

case $1 in
signed)
	debuild
	;;
upload)
	dput -c ../dput.cf pithos-lucid "../pithos_${VERSION}_source.changes"
	;;
unsigned|*)
	debuild -us -uc
	;;
esac
