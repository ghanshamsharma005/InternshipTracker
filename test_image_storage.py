import io
import unittest
from datetime import datetime, timezone
from app import create_app
from database.db import db
from models import User, UserProfileImage

class TestImageDatabaseStorage(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_image_blob_stored_directly_in_database(self):
        """
        Tests storing and retrieving raw binary data (BLOB) from the database table.
        """
        user = User(
            name="Marie Curie",
            email="marie@example.com",
            password_hash="hash123",
            role="student"
        )
        db.session.add(user)
        db.session.commit()

        # Dummy binary image data (e.g. 1x1 transparent PNG or sample bytes)
        sample_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4'
        
        profile_img = UserProfileImage(
            user_id=user.id,
            filename="marie_avatar.png",
            mimetype="image/png",
            image_data=sample_bytes
        )
        db.session.add(profile_img)
        db.session.commit()

        # Query back from SQLite database
        fetched_img = UserProfileImage.query.filter_by(user_id=user.id).first()
        self.assertIsNotNone(fetched_img)
        self.assertEqual(fetched_img.filename, "marie_avatar.png")
        self.assertEqual(fetched_img.mimetype, "image/png")
        self.assertEqual(fetched_img.image_data, sample_bytes)
        self.assertEqual(user.profile_image.image_data, sample_bytes)

    def test_cascade_delete_removes_image_blob(self):
        """
        Tests that deleting the user automatically cascades and deletes the image BLOB.
        """
        user = User(
            name="Pierre Curie",
            email="pierre@example.com",
            password_hash="hash123",
            role="faculty"
        )
        db.session.add(user)
        db.session.commit()

        profile_img = UserProfileImage(
            user_id=user.id,
            filename="pierre.jpg",
            mimetype="image/jpeg",
            image_data=b'\xff\xd8\xff\xe0samplejpegbytes'
        )
        db.session.add(profile_img)
        db.session.commit()

        # Delete user
        db.session.delete(user)
        db.session.commit()

        # Verify image BLOB was also deleted by foreign key cascade
        orphaned = UserProfileImage.query.filter_by(user_id=user.id).first()
        self.assertIsNone(orphaned)

    def test_get_user_image_route(self):
        """
        Tests streaming stored binary image from the HTTP endpoint.
        """
        user = User(
            name="Nikola Tesla",
            email="nikola@example.com",
            password_hash="hash123",
            role="student"
        )
        db.session.add(user)
        db.session.commit()

        # Before image upload: should return default SVG avatar
        res_default = self.client.get(f'/user/image/{user.id}')
        self.assertEqual(res_default.status_code, 200)
        self.assertIn('image/svg+xml', res_default.content_type)

        # Upload image to database
        sample_bytes = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        profile_img = UserProfileImage(
            user_id=user.id,
            filename="tesla.gif",
            mimetype="image/gif",
            image_data=sample_bytes
        )
        db.session.add(profile_img)
        db.session.commit()

        # After upload: should stream the exact GIF bytes
        res_uploaded = self.client.get(f'/user/image/{user.id}')
        self.assertEqual(res_uploaded.status_code, 200)
        self.assertEqual(res_uploaded.data, sample_bytes)
        self.assertIn('image/gif', res_uploaded.content_type)

    def test_upload_and_delete_profile_image_flow(self):
        """
        Tests full HTTP POST upload and delete workflow.
        """
        user = User(
            name="Ada Lovelace",
            email="ada@example.com",
            password_hash="hash123",
            role="student"
        )
        db.session.add(user)
        db.session.commit()

        # Simulate login session
        with self.client.session_transaction() as sess:
            sess['user_id'] = user.id
            sess['role'] = 'student'
            sess['user_name'] = user.name

        # Test uploading file
        file_bytes = b'FAKEPNGDATA123456'
        data = {
            'profile_image': (io.BytesIO(file_bytes), 'my_avatar.png')
        }
        res = self.client.post('/profile/upload-image', data=data, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Verify stored in DB
        saved = UserProfileImage.query.filter_by(user_id=user.id).first()
        self.assertIsNotNone(saved)
        self.assertEqual(saved.image_data, file_bytes)
        self.assertEqual(saved.filename, 'my_avatar.png')

        # Test delete image
        res_del = self.client.post('/profile/delete-image', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertIsNone(UserProfileImage.query.filter_by(user_id=user.id).first())

if __name__ == '__main__':
    unittest.main()
