// What's in the Bin? Weekly log (Google Form)
// One response per site per week, about 5 minutes.
//
// How to use:
//   1. Go to script.google.com > New project, delete the sample code, paste this file.
//   2. Click Run (function: createWeeklyLogForm) and approve the permissions.
//   3. Open View > Logs (or the Execution log) for the form's edit link and share link.
//   4. Add question 8 (photo) by hand: Google's script tools can't create file-upload questions.
//      Open the edit link, click +, choose "File upload", title it "Contamination photo",
//      allow Images only, max 1 file, and drag it between questions 7 and 9.
//      File upload requires people to sign in with a Google account.

function createWeeklyLogForm() {
  var form = FormApp.create("What's in the Bin? Weekly Log");
  form.setDescription(
    "Fresno State student plastic pilot. One response per site per week, about 5 minutes. " +
    "Look into the bins from the top; don't reach in with bare hands.");

  // 1. Site
  form.addListItem()
    .setTitle("Site")
    .setChoiceValues(["Fresno State Library", "McLane Hall", "Science II", "University Dining Hall"])
    .setRequired(true);

  // 2. Date
  form.addDateItem().setTitle("Date").setRequired(true);

  // 3-4. Fill levels
  var fill = ["Empty", "1/4", "1/2", "3/4", "Full", "Overflowing"];
  form.addListItem().setTitle("Trash bin fill level")
    .setChoiceValues(fill).setRequired(true);
  form.addListItem().setTitle("Recycling bin fill level")
    .setHelpText("Choose \"No recycling bin\" at the comparison sites.")
    .setChoiceValues(fill.concat(["No recycling bin"])).setRequired(true);

  // 5. Bagged trash
  form.addMultipleChoiceItem().setTitle("Bagged trash in the recycling bin?")
    .setChoiceValues(["Yes", "No"]).setRequired(true);

  // 6. Wrong-bin items
  form.addCheckboxItem()
    .setTitle("Single-use plastic items in the wrong bin")
    .setHelpText("Check every item you saw in the wrong bin.")
    .setChoiceValues(["Plastic bags", "Cups", "Lids", "Straws", "Clamshells and to-go containers",
                      "Utensils", "Bottles in trash", "Wrappers and film"])
    .showOtherOption(true);

  // 7. Most common item
  form.addTextItem().setTitle("Most common wrong-bin item this week").setRequired(true);

  // 8. Contamination photo: add by hand (see step 4 at the top).

  // 9. Notes
  form.addParagraphTextItem().setTitle("Notes");

  Logger.log("Edit link: " + form.getEditUrl());
  Logger.log("Share link: " + form.getPublishedUrl());
  Logger.log("Next: add question 8, a File upload question titled \"Contamination photo\" (Images only, 1 file).");
}
