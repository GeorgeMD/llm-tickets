import unittest
import tempfile
from pathlib import Path
import shutil

from ltk import store, utils

class TestStore(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.project_root = Path(self.test_dir)
        self.tickets_root = store.init_project(self.project_root)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_init_project(self):
        self.assertTrue(self.tickets_root.exists())
        self.assertTrue((self.tickets_root / store.EPICS_FILE).exists())

    def test_create_nested_epics_and_pathing(self):
        # Create parent epic
        parent_id = store.create_epic(self.tickets_root, "Parent Epic")
        # Create nested child epic
        child_id = store.create_epic(self.tickets_root, "Child Epic", parent_id=parent_id)
        
        epics = store.load_epics(self.tickets_root)
        self.assertEqual(epics[child_id]["parent"], parent_id)
        
        # Verify physical path
        child_path = store.get_epic_path(self.tickets_root, child_id, epics)
        expected_path = self.tickets_root / parent_id / child_id
        self.assertEqual(child_path.resolve(), expected_path.resolve())
        self.assertTrue(child_path.exists())

    def test_epic_dependencies_and_cycles(self):
        # Sibling epics
        epic_a = store.create_epic(self.tickets_root, "Epic A")
        epic_b = store.create_epic(self.tickets_root, "Epic B")
        
        # Add dependency
        store.add_epic_dependencies(self.tickets_root, epic_b, [epic_a])
        epics = store.load_epics(self.tickets_root)
        self.assertIn(epic_a, epics[epic_b]["depends"])
        self.assertEqual(epics[epic_b]["status"], "blocked")
        
        # Cycle detection: Epic A depending on Epic B should fail
        with self.assertRaises(ValueError):
            store.add_epic_dependencies(self.tickets_root, epic_a, [epic_b])

    def test_epic_dependencies_different_levels(self):
        # Epics can only depend on sibling epics at the same level
        parent_id = store.create_epic(self.tickets_root, "Parent")
        child_id = store.create_epic(self.tickets_root, "Child", parent_id=parent_id)
        epic_other = store.create_epic(self.tickets_root, "Other")
        
        with self.assertRaises(ValueError):
            store.add_epic_dependencies(self.tickets_root, child_id, [epic_other])

    def test_epic_status_propagation(self):
        # Parent is blocked -> Child is blocked
        parent_a = store.create_epic(self.tickets_root, "Parent A")
        parent_b = store.create_epic(self.tickets_root, "Parent B")
        
        # parent_b depends on parent_a
        store.add_epic_dependencies(self.tickets_root, parent_b, [parent_a])
        
        child_b = store.create_epic(self.tickets_root, "Child B", parent_id=parent_b)
        
        epics = store.load_epics(self.tickets_root)
        # parent_b is blocked directly
        self.assertEqual(store.get_effective_epic_status(self.tickets_root, parent_b, epics), "blocked")
        # child_b is blocked effectively because parent_b is blocked
        self.assertEqual(store.get_effective_epic_status(self.tickets_root, child_b, epics), "blocked")

    def test_ticket_status_propagation_and_blocking(self):
        parent_a = store.create_epic(self.tickets_root, "Parent A")
        parent_b = store.create_epic(self.tickets_root, "Parent B")
        
        # parent_b depends on parent_a (so parent_b is blocked)
        store.add_epic_dependencies(self.tickets_root, parent_b, [parent_a])
        
        # Create ticket in parent_b (which is blocked)
        ticket_id = store.create_ticket(self.tickets_root, parent_b, "Ticket in B")
        
        epics = store.load_epics(self.tickets_root)
        tickets = store.load_tickets(self.tickets_root, parent_b)
        
        # Stored ticket status is open
        self.assertEqual(tickets[ticket_id]["status"], "open")
        
        # Effective ticket status is blocked because epic is blocked
        eff_status = store.get_effective_ticket_status(self.tickets_root, parent_b, tickets[ticket_id], epics)
        self.assertEqual(eff_status, "blocked")
        
        # Trying to start the ticket should fail
        with self.assertRaises(ValueError):
            store.start_ticket(self.tickets_root, parent_b, ticket_id)

    def test_close_epic_unblocking_siblings(self):
        epic_a = store.create_epic(self.tickets_root, "Epic A")
        epic_b = store.create_epic(self.tickets_root, "Epic B")
        
        # epic_b depends on epic_a
        store.add_epic_dependencies(self.tickets_root, epic_b, [epic_a])
        
        epics = store.load_epics(self.tickets_root)
        self.assertEqual(epics[epic_b]["status"], "blocked")
        
        # Start and close epic_a
        store.start_epic(self.tickets_root, epic_a)
        unblocked = store.close_epic(self.tickets_root, epic_a)
        
        self.assertEqual(unblocked, [epic_b])
        epics = store.load_epics(self.tickets_root)
        self.assertEqual(epics[epic_b]["status"], "open")
        self.assertEqual(epics[epic_a]["status"], "closed")

    def test_delete_epic_recursive(self):
        parent = store.create_epic(self.tickets_root, "Parent")
        child = store.create_epic(self.tickets_root, "Child", parent_id=parent)
        
        epics = store.load_epics(self.tickets_root)
        self.assertIn(parent, epics)
        self.assertIn(child, epics)
        
        store.delete_epic(self.tickets_root, parent)
        
        epics = store.load_epics(self.tickets_root)
        self.assertNotIn(parent, epics)
        self.assertNotIn(child, epics)

    def test_format_tree_output(self):
        parent_id = store.create_epic(self.tickets_root, "Parent Epic")
        child_id = store.create_epic(self.tickets_root, "Child Epic", parent_id=parent_id)
        other_id = store.create_epic(self.tickets_root, "Other Epic")
        
        t1 = store.create_ticket(self.tickets_root, parent_id, "Ticket in Parent")
        t2 = store.create_ticket(self.tickets_root, child_id, "Ticket in Child")
        
        epics = store.load_epics(self.tickets_root)
        tickets_by_epic = {
            parent_id: store.load_tickets(self.tickets_root, parent_id),
            child_id: store.load_tickets(self.tickets_root, child_id),
            other_id: store.load_tickets(self.tickets_root, other_id),
        }
        
        output = utils.format_tree(self.tickets_root, epics, tickets_by_epic)
        
        self.assertIn("Parent Epic", output)
        self.assertIn("Child Epic", output)
        self.assertIn("Other Epic", output)
        self.assertIn("Ticket in Parent", output)
        self.assertIn("Ticket in Child", output)

    def test_utf8_bom_handling(self):
        epic_id = store.create_epic(self.tickets_root, "Epic A")
        ticket_id = store.create_ticket(self.tickets_root, epic_id, "Ticket A")
        
        # Write ticket file with UTF-8 BOM manually
        epics = store.load_epics(self.tickets_root)
        epic_path = store.get_epic_path(self.tickets_root, epic_id, epics)
        ticket_file = epic_path / f"{ticket_id}.md"
        
        # Prepend BOM manually
        ticket_file.write_text("\ufeff# Ticket A\nSome content", encoding="utf-8")
        
        # Read ticket
        content = store.read_ticket(self.tickets_root, epic_id, ticket_id)
        self.assertEqual(content, "# Ticket A\nSome content")

