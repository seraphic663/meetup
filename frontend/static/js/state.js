import { ST_AVAIL } from './constants.js';

export const state = {
  SID: null,
  S: null,
  ME: null,
  ME_NAME: '',
  AUTO_JOIN: false,
  myAvail: {},
  myRemark: '',
  manageParticipants: [],
  layout: 'pr',
  collapsed: true,
  userPrefs: { layout: 'pr', collapsed: true },
  settingsDraft: { layout: 'pr', collapsed: true },
  drag: { on: false, fillTo: ST_AVAIL, col: -1, lastKey: '' },
  pollT: null,
  saveT: null,
  remarkSaveT: null,
  tutorialStep: 0,
  tags: [],
  pickedJoinName: null,
};
