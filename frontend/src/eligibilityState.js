const initialEligibilityState = {
  occupation: '',
  step: 1,
  questions: [],
  answers: {},
  results: null,
}

function visibleEligibilityQuestions(occupation, questions, answers, step = 2) {
  if (step !== 2 || !occupation || !Array.isArray(questions)) return []
  return questions.filter(question => {
    if (occupation === 'student') {
      const technicalTrack = ['technical_degree', 'technical_diploma'].includes(answers.study_track)
      if (['institution_approved', 'income_certificate', 'girls_limit'].includes(question.id)) return technicalTrack && answers.gender === 'female'
      if (question.id === 'school_stage') return answers.study_track === 'school'
    }
    if (occupation === 'small_business') {
      if (question.id === 'vendor_identified') return answers.enterprise_stage === 'street_vendor' || answers.enterprise_type === 'vendor'
      if (question.id === 'notified_artisan_trade') return answers.enterprise_stage === 'traditional_artisan' || answers.enterprise_type === 'traditional_trade'
    }
    if (occupation === 'general' && question.id === 'housing_prior_benefit') return answers.pucca_house !== 'yes'
    return true
  })
}

function eligibilityReducer(state, action) {
  switch (action.type) {
    case 'PROFILE_CHANGED':
      if (action.occupation === state.occupation) return state
      return { ...initialEligibilityState, occupation: action.occupation }
    case 'QUESTIONS_LOADED':
      return { ...state, step: 2, questions: action.questions }
    case 'ANSWER_CHANGED': {
      const answers = { ...state.answers, [action.id]: action.value }
      if (action.id === 'study_track') {
        if (!['technical_degree', 'technical_diploma'].includes(action.value)) {
          delete answers.institution_approved; delete answers.income_certificate; delete answers.girls_limit
        }
        if (action.value !== 'school') delete answers.school_stage
      }
      if (action.id === 'gender' && action.value !== 'female') delete answers.girls_limit
      if (action.id === 'enterprise_stage') {
        if (action.value !== 'street_vendor') delete answers.vendor_identified
        if (action.value !== 'traditional_artisan') delete answers.notified_artisan_trade
      }
      if (action.id === 'pucca_house' && action.value === 'yes') delete answers.housing_prior_benefit
      return { ...state, answers }
    }
    case 'RESULTS_LOADED':
      return { ...state, step: 3, results: action.results }
    case 'BACK':
      return { ...state, step: Math.max(1, state.step - 1) }
    case 'CHECK_AGAIN':
      return { ...initialEligibilityState }
    default:
      return state
  }
}

export { visibleEligibilityQuestions, initialEligibilityState, eligibilityReducer }
