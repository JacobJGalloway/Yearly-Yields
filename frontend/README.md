# Yearly Yields — Frontend

Angular v21 + Angular Material

## Setup (run Monday)

```bash
cd frontend
ng new yearly-yields-ui --routing --style=scss --standalone
cd yearly-yields-ui
ng add @angular/material
npm install @ngrx/store @ngrx/effects @ngrx/entity @ngrx/router-store @ngrx/store-devtools
```

## Structure
See architecture plan — features are lazy-loaded modules under `src/app/features/`.
NgRx used only for `auth` and `alerts` global state.
