import { ST_AVAIL } from './constants.js';

export const state = {
  SID: null,
  S: null,
  ME: null,
  AUTO_JOIN: false,
  myAvail: {},
  myRemark: '',
  layout: 'tr',
  collapsed: true,
  drag: { on: false, fillTo: ST_AVAIL, col: -1, lastKey: '' },
  pollT: null,
  saveT: null,
  remarkSaveT: null,
  tutorialStep: 0,
  tags: [],
  pickedJoinName: null,
};
