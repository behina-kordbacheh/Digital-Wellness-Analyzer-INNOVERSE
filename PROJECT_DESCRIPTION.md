# Project Description

## Digital Wellness Analyzer

The Digital Wellness Analyzer is an AI-powered system that analyzes digital device usage to promote healthier technology habits. The system uses machine learning and data analytics to identify screen-time patterns, estimate digital behavior risk, estimate weekend screen time from current behavior, segment users into behavioral groups, and generate personalized wellness recommendations.

The project is designed to move beyond generic advice. Instead of only telling users to reduce social media, it recommends realistic replacement activities based on their role, available time, personal goal, preferred activity style, peak scrolling period, and the reason they typically open social media.

## Core Technology

- Machine Learning
- Data Analytics
- Flask Web Application
- HTML / CSS / JavaScript
- Local SQLite database
- Local PDF reporting

## Main Features

### 1. Analyze Device Usage Patterns

- Analyze daily screen time
- Analyze social-media and gaming time
- Analyze work/study time and sleep time
- Analyze notification volume and app opening frequency
- Compare user values with dataset-relative percentiles
- Show current and local historical behavior trends

### 2. Detect Higher-Risk Digital Behavior

- Random Forest classification
- Tuned decision threshold
- SHAP explanation of individual predictions
- Late-night scrolling flag from user context
- High notification-volume detection
- Weekend screen-time pattern detection

### 3. Predict Screen-Time Balance

- Random Forest regression estimates estimated weekend screen time
- UI charts visualize current time allocation
- Local history can show how model risk changes between check-ins

### 4. Generate Wellness Suggestions

- Screen-free block suggestions
- Focus-session suggestions
- Notification management suggestions
- Late-night wind-down suggestions
- Offline activity replacement suggestions
- Focus-software suggestions

### 5. Personalize Recommendations

Personalization inputs include:

- occupation / role
- available free time
- main wellness goal
- preferred activity style
- peak scrolling time
- social-media trigger
- main device platform

These fields personalize the recommendation layer only. They are not used as untrained classifier features.

### 6. Local Reports and Progress Tracking

- Downloadable PDF analysis report
- Next check-in time inside the application and PDF
- Local SQLite analysis history
- Local Recommendation Acceptance Rate
- Local User Satisfaction Score
- Manual Telegram report-summary sharing

## Expected Outputs

- Digital behavior report
- Model Risk Score
- Lower-risk / higher-risk pattern classification
- Weekend screen-time estimate
- Behavior cluster
- SHAP explanation
- Personalized recommendations
- Suggested focus software
- Local historical trend chart
- PDF report

## Future Enhancements

- Real device telemetry integration
- Wearable integration
- Optional AI coaching chatbot
- True per-user time-series modeling when longitudinal data becomes available
- Cross-device synchronization with explicit user consent
- Gamified wellness achievements
