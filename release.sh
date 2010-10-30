#!/bin/bash

REVNO=$(bzr revno)
VERSIONBASE=$(python pithos/pithosconfig.py)
VERSION="$VERSIONBASE~bzr$REVNO"

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
	debuild -S
	dput -c ../dput.cf pithos-lucid "../pithos_${VERSION}_source.changes"
	;;
tgz)
	NAME=pithos_$VERSIONBASE
	FNAME=../release/${NAME}.tar
	FNAME2=../release/${NAME}.tgz
	bzr export $FNAME
	tar -f $FNAME --delete $NAME/debian
	gzip $FNAME
	mv $FNAME.gz $FNAME2
	gpg --sign $FNAME2
	;;
unsigned|*)
	debuild -us -uc
	;;
esac
