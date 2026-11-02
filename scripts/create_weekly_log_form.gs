// What's in the Bin? Weekly log (Google Form)
// One response per site per week, about 5 minutes.
//
// What it records: how full each bin is, and COUNTS of the visible single-use plastic items
// in the wrong bin (recyclable plastic in the trash, and bags or trash in the recycling).
// Counts, not checkmarks, so the answers can be added up, compared week to week, and charted.
//
// How to use:
//   1. Go to script.google.com > New project, delete the sample code, paste this file.
//   2. Edit SITES below for your campus (Fresno State's four pilot sites are filled in).
//   3. Click Run (function: createWeeklyLogForm) and approve the permissions.
//   4. Open View > Logs (or the Execution log) for the form's edit link and share link.
//   5. Add the photo question by hand: Google's script tools can't create file-upload questions.
//      Open the edit link, click +, choose "File upload", title it "Contamination photo",
//      allow Images only, max 1 file, and drag it just above "Notes".
//      File upload requires people to sign in with a Google account.
//   6. In the form's Responses tab, click "Link to Sheets" so every answer lands in a Google Sheet.

// Our pilot sites. Another campus: replace these with your own site names.
var SITES = ["Fresno State Library", "McLane Hall", "Science II", "University Dining Hall"];

// Single-use plastic items that can usually be recycled. Check your hauler's accepted list
// and change this if your hauler takes something different.
var RECYCLABLE_IN_TRASH = ["Plastic bottles", "Plastic cups", "Clamshells and to-go containers", "Lids"];

// Things that don't belong in the recycling bin.
var WRONG_IN_RECYCLING = ["Plastic bags and film", "Straws", "Utensils", "Food-soiled containers"];

function createWeeklyLogForm() {
  var form = FormApp.create("What's in the Bin? Weekly Log");
  form.setDescription(
    "Student plastic pilot. One response per site per week, about 5 minutes. " +
    "Count only what you can see from the top. Don't reach in.");

  // Every count box only accepts whole numbers (0, 1, 2, ...), so the data stays clean.
  var wholeNumber = FormApp.createTextValidation()
    .setHelpText("Enter a whole number (0 if none).")
    .requireWholeNumber()
    .build();

  // --- About this check ---
  form.addListItem().setTitle("Site").setChoiceValues(SITES).setRequired(true);
  form.addDateItem().setTitle("Date").setRequired(true);
  form.addTimeItem().setTitle("Time of check").setRequired(true);
  form.addTextItem().setTitle("Your initials").setRequired(true);

  // Lets us compare each site with its own first weeks (the baseline) and with the other sites.
  form.addMultipleChoiceItem()
    .setTitle("Pilot phase at this site")
    .setChoiceValues(["Baseline (first 3 weeks, no changes yet)",
                      "Test site (paired bins and signs in place)",
                      "Comparison site (no changes)"])
    .setRequired(true);

  // --- How full the bins are ---
  var fill = ["Empty", "1/4", "1/2", "3/4", "Full", "Overflowing"];
  form.addListItem().setTitle("Trash bin fill level").setChoiceValues(fill).setRequired(true);
  form.addListItem().setTitle("Recycling bin fill level")
    .setHelpText("Choose \"No recycling bin\" if this site doesn't have one.")
    .setChoiceValues(fill.concat(["No recycling bin"])).setRequired(true);

  // --- Counts in the TRASH bin: recyclable plastic that ended up in the trash ---
  form.addSectionHeaderItem()
    .setTitle("In the TRASH bin")
    .setHelpText("Count the visible items that could have been recycled.");
  RECYCLABLE_IN_TRASH.forEach(function (item) {
    form.addTextItem().setTitle("Trash bin: " + item).setValidation(wholeNumber).setRequired(true);
  });

  // --- Counts in the RECYCLING bin: things that don't belong there ---
  form.addSectionHeaderItem()
    .setTitle("In the RECYCLING bin")
    .setHelpText("Skip this part if there's no recycling bin. Count the visible items that don't belong.");
  form.addMultipleChoiceItem().setTitle("Bagged trash in the recycling bin?")
    .setChoiceValues(["Yes", "No", "No recycling bin"]).setRequired(true);
  WRONG_IN_RECYCLING.forEach(function (item) {
    // Not required, because comparison sites may not have a recycling bin.
    form.addTextItem().setTitle("Recycling bin: " + item).setValidation(wholeNumber);
  });

  // --- Where the items came from, so the right vendor gets the swap request ---
  form.addCheckboxItem()
    .setTitle("Where did the wrong-bin items come from? (if you can tell)")
    .setChoiceValues(["Dining Hall", "Campus coffee shop", "Other campus vendor", "Off campus", "Can't tell"])
    .showOtherOption(true);

  // The photo question goes here: add it by hand (step 5 at the top).

  form.addParagraphTextItem().setTitle("Notes");

  Logger.log("Edit link: " + form.getEditUrl());
  Logger.log("Share link: " + form.getPublishedUrl());
  Logger.log("Next: add a File upload question titled \"Contamination photo\" (Images only, 1 file), " +
             "then link the form to a Google Sheet in the Responses tab.");
}
