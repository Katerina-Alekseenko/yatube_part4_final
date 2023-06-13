import shutil
import tempfile

from http import HTTPStatus
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from ..models import Comment, Group, Post, User


class PostCreateFormTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        settings.MEDIA_ROOT = tempfile.mkdtemp(dir=settings.BASE_DIR)
        cls.user = User.objects.create(username='NoName')
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
        )
        cls.group = Group.objects.create(
            title='test_title',
            slug='first',
            description='test_description'
        )
        cls.post_edit = Post.objects.create(
            text='Тестовый текст',
            author=cls.user,
            group=cls.group
        )
        cls.group_edit = Group.objects.create(
            title='Тестовая группа',
            slug='test-group',
            description='Описание'
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(settings.MEDIA_ROOT, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.guest_client = Client()
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)

    def test_create_post(self):
        """Проверка формы создания нового поста."""
        posts_count = Post.objects.count()
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x02\x00'
            b'\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
            b'\x00\x00\x00\x2C\x00\x00\x00\x00'
            b'\x02\x00\x01\x00\x00\x02\x02\x0C'
            b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        form_data = {
            'text': 'Тестовый пост',
            'group': self.group.pk,
            'image': uploaded
        }
        response = self.authorized_client.post(
            reverse('posts:post_create'),
            data=form_data,
            follow=True,
        )
        self.assertRedirects(response, reverse(
            'posts:profile', kwargs={'username': f'{self.user}'})
        )
        self.assertEqual(Post.objects.count(), posts_count + 1)
        self.assertTrue(Post.objects.filter(
            text='Тестовый пост',
            group=self.group.pk,
            image='posts/small.gif').exists()
        )
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_edit_post(self):
        """Проверка формы редактирования поста"""
        old_text = self.post_edit
        form_data = {'text': 'Текст записанный в форму',
                     'group': self.group_edit.id}
        response = self.authorized_client.post(
            reverse('posts:post_edit', kwargs={'post_id': self.post_edit.pk}),
            data=form_data,
            follow=True,
        )
        error_post = 'Данные поста не совпадают'
        self.assertTrue(Post.objects.filter(
            author=self.user,
            group=self.group_edit.id,
            pub_date=self.post_edit.pub_date).exists(), error_post
        )
        error_change = 'Пользователь не может изменить содержание поста'
        self.assertNotEqual(old_text.text, form_data['text'], error_change)
        self.assertEqual(response.status_code, HTTPStatus.OK)

    def test_add_posts_comment(self):
        """Проверяем создание комментария"""
        comment_count = Comment.objects.count()
        new_comment = {
            'text': 'comment text',
        }
        self.authorized_client.post(
            reverse('posts:add_comment', args=[self.post.id]),
            data=new_comment,
            follow=True,
        )
        self.assertEqual(Comment.objects.count(), comment_count + 1)

    def test_comment_create_login_required(self):
        """Неавторизованный пользователь не может комментировать."""
        response = self.client.get(
            reverse('posts:add_comment', kwargs={'post_id': self.post.id})
        )
        self.assertRedirects(
            response,
            reverse("users:login") + '?next=' + reverse(
                "posts:add_comment",
                kwargs={"post_id": self.post.id})
        )
