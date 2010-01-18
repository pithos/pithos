 %module piano
 %{
 /* Includes the header in the wrapper code */
 
 #include "piano.h"
 %}
 
%include "typemaps.i"

typedef struct PianoUserInfo {
	char *webAuthToken;
	char *listenerId;
	char *authToken;
} PianoUserInfo_t;

typedef struct PianoStation {
	char isCreator;
	char isQuickMix;
	char useQuickMix; /* station will be included in quickmix */
	char *name;
	char *id;
	char *idToken;
	struct PianoStation *next;
} PianoStation_t;

typedef enum {PIANO_RATE_BAN, PIANO_RATE_LOVE, PIANO_RATE_NONE}
		PianoSongRating_t;

/* UNKNOWN should be 0, because memset sets audio format to 0 */
typedef enum {PIANO_AF_UNKNOWN = 0, PIANO_AF_AACPLUS, PIANO_AF_MP3,
		PIANO_AF_MP3_HI} PianoAudioFormat_t;

typedef struct PianoSong {
	char *artist;
	char *matchingSeed;
	float fileGain;
	PianoSongRating_t rating;
	char *stationId;
	char *album;
	char *userSeed;
	char *audioUrl;
	char *musicId;
	char *title;
	char *focusTraitId;
	char *identity;
	char *artRadio;
	char *songDetailURL;
	PianoAudioFormat_t audioFormat;
	struct PianoSong *next;
} PianoSong_t;

/* currently only used for search results */
typedef struct PianoArtist {
	char *name;
	char *musicId;
	int score;
	struct PianoArtist *next;
} PianoArtist_t;

typedef struct PianoGenreCategory {
	char *name;
	PianoStation_t *stations;
	struct PianoGenreCategory *next;
} PianoGenreCategory_t;

typedef struct PianoHandle {
	WaitressHandle_t waith;
	char routeId[9];
	PianoUserInfo_t user;
	/* linked lists */
	PianoStation_t *stations;
	PianoGenreCategory_t *genreStations;
} PianoHandle_t;

typedef struct PianoSearchResult {
	PianoSong_t *songs;
	PianoArtist_t *artists;
} PianoSearchResult_t;

typedef enum {PIANO_RET_OK, PIANO_RET_ERR, PIANO_RET_XML_INVALID,
		PIANO_RET_AUTH_TOKEN_INVALID, PIANO_RET_AUTH_USER_PASSWORD_INVALID,
		PIANO_RET_NET_ERROR, PIANO_RET_NOT_AUTHORIZED,
		PIANO_RET_PROTOCOL_INCOMPATIBLE, PIANO_RET_READONLY_MODE,
		PIANO_RET_STATION_CODE_INVALID, PIANO_RET_IP_REJECTED,
		PIANO_RET_STATION_NONEXISTENT, PIANO_RET_OUT_OF_MEMORY,
		PIANO_RET_OUT_OF_SYNC} PianoReturn_t;

void PianoInit (PianoHandle_t *);
void PianoDestroy (PianoHandle_t *);
void PianoDestroyPlaylist (PianoSong_t *);
void PianoDestroySearchResult (PianoSearchResult_t *);
PianoReturn_t PianoConnect (PianoHandle_t *, const char *, const char *);

PianoReturn_t PianoGetStations (PianoHandle_t *);

%typemap (in,numinputs=0) PianoSong_t** (PianoSong_t *temp)
{
	temp = 0;
    $1 = &temp;
}

%typemap (argout) PianoSong_t**
{
    PyObject *obj = SWIG_NewPointerObj(*$1, SWIGTYPE_p_PianoSong, 0);
    $result = PyTuple_Pack(2, $result, obj);
}

PianoReturn_t PianoGetPlaylist (PianoHandle_t *, const char *,
		PianoAudioFormat_t, PianoSong_t **ret);

PianoReturn_t PianoRateTrack (PianoHandle_t *, PianoSong_t *,
		PianoSongRating_t);
PianoReturn_t PianoMoveSong (PianoHandle_t *, const PianoStation_t *,
		const PianoStation_t *, const PianoSong_t *);
PianoReturn_t PianoRenameStation (PianoHandle_t *, PianoStation_t *,
		const char *);
PianoReturn_t PianoDeleteStation (PianoHandle_t *, PianoStation_t *);
PianoReturn_t PianoSearchMusic (PianoHandle_t *, const char *,
		PianoSearchResult_t *);
PianoReturn_t PianoCreateStation (PianoHandle_t *, const char *,
		const char *);
PianoReturn_t PianoStationAddMusic (PianoHandle_t *, PianoStation_t *,
		const char *);
PianoReturn_t PianoSongTired (PianoHandle_t *, const PianoSong_t *);
PianoReturn_t PianoSetQuickmix (PianoHandle_t *);
PianoStation_t *PianoFindStationById (PianoStation_t *, const char *);
PianoReturn_t PianoGetGenreStations (PianoHandle_t *);
PianoReturn_t PianoTransformShared (PianoHandle_t *, PianoStation_t *);
PianoReturn_t PianoExplain (PianoHandle_t *, const PianoSong_t *, char **OUTPUT);
const char *PianoErrorToStr (PianoReturn_t);
PianoReturn_t PianoSeedSuggestions (PianoHandle_t *, const char *,
		unsigned int, PianoSearchResult_t *);
