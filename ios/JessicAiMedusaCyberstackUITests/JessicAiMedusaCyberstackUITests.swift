import XCTest

final class JessicAiMedusaCyberstackUITests: XCTestCase {

    var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["--uitesting", "--skip-auth"]
        app.launch()
    }

    override func tearDownWithError() throws {
        app = nil
    }

    // MARK: - Auth Screen Tests

    func testAuthScreenDisplaysCorrectTitle() {
        let jessicAiLabel = app.staticTexts["JessicAi"]
        XCTAssertTrue(jessicAiLabel.waitForExistence(timeout: 5))
    }

    func testAuthScreenHasAuthenticateButton() {
        let authenticateButton = app.buttons["Authenticate"]
        XCTAssertTrue(authenticateButton.waitForExistence(timeout: 5))
    }

    func testAuthScreenSubtitleDisplayed() {
        let subtitle = app.staticTexts["Medusa Cyberstack"]
        XCTAssertTrue(subtitle.waitForExistence(timeout: 5))
    }

    // MARK: - Tab Navigation Tests

    func testDashboardTabExists() {
        // After auth, dashboard should be visible
        let dashboardTab = app.tabBars.buttons["Dashboard"]
        XCTAssertTrue(dashboardTab.waitForExistence(timeout: 10))
    }

    func testLoRaTabNavigationExists() {
        let loraTab = app.tabBars.buttons["LoRa"]
        XCTAssertTrue(loraTab.waitForExistence(timeout: 10))
    }

    func testBLETabExists() {
        let bleTab = app.tabBars.buttons["BLE"]
        XCTAssertTrue(bleTab.waitForExistence(timeout: 10))
    }

    func testGeofenceTabExists() {
        let geofenceTab = app.tabBars.buttons["Geofence"]
        XCTAssertTrue(geofenceTab.waitForExistence(timeout: 10))
    }

    func testAITabExists() {
        let aiTab = app.tabBars.buttons["JessicAi"]
        XCTAssertTrue(aiTab.waitForExistence(timeout: 10))
    }

    func testSettingsTabExists() {
        let settingsTab = app.tabBars.buttons["Settings"]
        XCTAssertTrue(settingsTab.waitForExistence(timeout: 10))
    }

    // MARK: - Dashboard Tests

    func testDashboardDisplaysNodeCount() {
        let dashboardTab = app.tabBars.buttons["Dashboard"]
        if dashboardTab.waitForExistence(timeout: 10) {
            dashboardTab.tap()
            let loRaMeshCard = app.staticTexts["LoRa Mesh"]
            XCTAssertTrue(loRaMeshCard.waitForExistence(timeout: 5))
        }
    }

    func testDashboardHasNavigationTitle() {
        let dashboardTab = app.tabBars.buttons["Dashboard"]
        if dashboardTab.waitForExistence(timeout: 10) {
            dashboardTab.tap()
            let title = app.navigationBars["Dashboard"]
            XCTAssertTrue(title.waitForExistence(timeout: 5))
        }
    }

    // MARK: - Settings Tests

    func testSettingsTabNavigation() {
        let settingsTab = app.tabBars.buttons["Settings"]
        if settingsTab.waitForExistence(timeout: 10) {
            settingsTab.tap()
            let settingsTitle = app.navigationBars["Settings"]
            XCTAssertTrue(settingsTitle.waitForExistence(timeout: 5))
        }
    }

    func testSettingsLockAppButton() {
        let settingsTab = app.tabBars.buttons["Settings"]
        if settingsTab.waitForExistence(timeout: 10) {
            settingsTab.tap()
            let lockButton = app.buttons["Lock App"]
            XCTAssertTrue(lockButton.waitForExistence(timeout: 5))
        }
    }

    // MARK: - LoRa Tests

    func testLoRaTabShowsMeshNodes() {
        let loraTab = app.tabBars.buttons["LoRa"]
        if loraTab.waitForExistence(timeout: 10) {
            loraTab.tap()
            let meshNodesHeader = app.staticTexts["MESH NODES"]
            XCTAssertTrue(meshNodesHeader.waitForExistence(timeout: 5))
        }
    }

    // MARK: - AI Tab Tests

    func testAITabShowsJessicAiTitle() {
        let aiTab = app.tabBars.buttons["JessicAi"]
        if aiTab.waitForExistence(timeout: 10) {
            aiTab.tap()
            let jessicAiLabel = app.staticTexts["JessicAi"]
            XCTAssertTrue(jessicAiLabel.waitForExistence(timeout: 5))
        }
    }

    func testAICommandInputExists() {
        let aiTab = app.tabBars.buttons["JessicAi"]
        if aiTab.waitForExistence(timeout: 10) {
            aiTab.tap()
            let commandField = app.textFields["Enter AI command…"]
            XCTAssertTrue(commandField.waitForExistence(timeout: 5))
        }
    }
}
