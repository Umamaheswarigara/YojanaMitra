import assert from 'node:assert/strict'
import test from 'node:test'
import { eligibilityReducer, initialEligibilityState, visibleEligibilityQuestions } from './eligibilityState.js'

test('back and continue preserve answers across step transitions', () => {
  let state = eligibilityReducer(initialEligibilityState, { type: 'PROFILE_CHANGED', occupation: 'student' })
  state = eligibilityReducer(state, { type: 'QUESTIONS_LOADED', questions: [{ id: 'gender' }] })
  state = eligibilityReducer(state, { type: 'ANSWER_CHANGED', id: 'gender', value: 'female' })
  state = eligibilityReducer(state, { type: 'BACK' })
  assert.equal(state.step, 1)
  assert.equal(state.answers.gender, 'female')
  state = eligibilityReducer(state, { type: 'QUESTIONS_LOADED', questions: [{ id: 'gender' }] })
  assert.equal(state.step, 2)
  assert.equal(state.answers.gender, 'female')
})

test('changing profile clears answers, previous questions, and prior results', () => {
  let state = eligibilityReducer(initialEligibilityState, { type: 'PROFILE_CHANGED', occupation: 'student' })
  state = eligibilityReducer(state, { type: 'QUESTIONS_LOADED', questions: [{ id: 'gender' }] })
  state = eligibilityReducer(state, { type: 'ANSWER_CHANGED', id: 'gender', value: 'female' })
  state = eligibilityReducer(state, { type: 'RESULTS_LOADED', results: { counts: {} } })
  state = eligibilityReducer(state, { type: 'BACK' })
  state = eligibilityReducer(state, { type: 'BACK' })
  state = eligibilityReducer(state, { type: 'PROFILE_CHANGED', occupation: 'farmer' })
  assert.equal(state.occupation, 'farmer')
  assert.equal(state.step, 1)
  assert.deepEqual(state.answers, {})
  assert.deepEqual(state.questions, [])
  assert.equal(state.results, null)
})

test('conditional questions are shown only when they apply and stale answers are removed', () => {
  const questions = [{ id: 'gender' }, { id: 'study_track' }, { id: 'institution_approved' }, { id: 'girls_limit' }, { id: 'school_stage' }]
  assert.deepEqual(visibleEligibilityQuestions('student', questions, { gender: 'male', study_track: 'technical_degree' }, 2).map(q => q.id), ['gender', 'study_track'])
  assert.deepEqual(visibleEligibilityQuestions('student', questions, { gender: 'female' }, 1), [])
  assert.deepEqual(visibleEligibilityQuestions('student', questions, { gender: 'female' }, 3), [])
  let state = { ...initialEligibilityState, occupation: 'student', answers: { institution_approved: 'yes', income_certificate: 'yes', girls_limit: 'no', school_stage: 'yes' } }
  state = eligibilityReducer(state, { type: 'ANSWER_CHANGED', id: 'study_track', value: 'other' })
  assert.deepEqual(state.answers, { study_track: 'other' })
})

test('check again resets the assessment to step one', () => {
  const state = eligibilityReducer({ ...initialEligibilityState, occupation: 'woman', step: 3, answers: { age_band: '18_40' }, results: {} }, { type: 'CHECK_AGAIN' })
  assert.deepEqual(state, initialEligibilityState)
})
